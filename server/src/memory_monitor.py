import asyncio
import psutil
import logging
from typing import Callable, Optional
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class MemoryMonitor:
    def __init__(
        self,
        profile_id: str,
        context: BrowserContext,
        threshold_mb: int,
        on_threshold_exceeded: Callable,
        browser_pid: Optional[int] = None  # New: Accept the Browser PID for accurate tracking
    ):
        self.profile_id = profile_id
        self.context = context
        self.threshold_mb = threshold_mb
        self.on_threshold_exceeded = on_threshold_exceeded
        self.browser_pid = browser_pid

        self.task: Optional[asyncio.Task] = None
        self.running = False

        self.current_memory_mb = 0
        self.cpu_percent = 0.0

    def start(self):
        """Start monitoring"""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor())
        logger.info(f"Started memory monitor for {self.profile_id}")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info(f"Stopped memory monitor for {self.profile_id}")

    async def _monitor(self):
        """Monitor memory usage"""
        while self.running:
            try:
                # Get memory usage
                memory_mb = await self._get_memory_usage()
                self.current_memory_mb = memory_mb

                # Get CPU usage
                cpu = await self._get_cpu_usage()
                self.cpu_percent = cpu

                # Check threshold
                if memory_mb > self.threshold_mb:
                    logger.warning(
                        f"Profile {self.profile_id} exceeded memory threshold: "
                        f"{memory_mb}MB > {self.threshold_mb}MB"
                    )
                    if self.on_threshold_exceeded:
                        self.on_threshold_exceeded()
                    break

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
                await asyncio.sleep(30)

    async def _get_memory_usage(self) -> int:
        """
        Get accurate memory usage in MB by tracking the browser process tree.
        Falls back to CDP if PID is not available.
        """
        try:
            # Method 1: Use PSUtil on the Browser Process Tree (Most Accurate)
            if self.browser_pid:
                try:
                    parent = psutil.Process(self.browser_pid)
                    memory_bytes = parent.memory_info().rss

                    # Sum memory of all child processes (renderers, GPU, extensions)
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            memory_bytes += child.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue

                    return int(memory_bytes / (1024 * 1024))

                except psutil.NoSuchProcess:
                    logger.warning(f"Browser process {self.browser_pid} not found for memory check.")
                    return 0
                except Exception as e:
                    logger.error(f"Psutil error: {e}")

            # Method 2: Fallback to CDP (Approximation) if PID not provided
            # Note: This is less accurate for total memory but better than nothing
            pages = self.context.pages
            if not pages:
                return 0

            # Try to get JS Heap Size as a proxy for memory usage
            try:
                page = pages[0]
                client = await page.context.new_cdp_session(page)
                # Get metrics from the page
                metrics = await client.send("Performance.getMetrics")

                # Look for JSHeapUsedSize
                heap_used = 0
                for m in metrics.get('metrics', []):
                    if m['name'] == 'JSHeapUsedSize':
                        heap_used = m['value']

                # This is only heap size, not total memory, so it's a lower bound estimate
                # Multiply by heuristic factor (e.g., 2x) to approximate total process size
                return int((heap_used * 2) / (1024 * 1024))

            except Exception as e:
                logger.error(f"CDP fallback memory check failed: {e}")
                return 0

        except Exception as e:
            logger.error(f"Critical error getting memory usage: {e}")
            return 0

    async def _get_cpu_usage(self) -> float:
        """
        Get accurate CPU usage percentage of the browser process tree.
        """
        try:
            if self.browser_pid:
                try:
                    parent = psutil.Process(self.browser_pid)
                    # Get CPU for parent
                    cpu_total = parent.cpu_percent(interval=0.1)

                    # Sum CPU of all children
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            cpu_total += child.cpu_percent(interval=0.1)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue

                    return cpu_total

                except psutil.NoSuchProcess:
                    return 0.0

            # Fallback: System-wide CPU (Not ideal for profile-specific)
            return psutil.cpu_percent(interval=0.1)

        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return 0.0

    def get_metrics(self) -> dict:
        """Get current metrics"""
        return {
            "memory_mb": self.current_memory_mb,
            "memory_limit_mb": self.threshold_mb,
            "cpu_percent": self.cpu_percent,
        }
