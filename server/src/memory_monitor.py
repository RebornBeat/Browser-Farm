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
        on_threshold_exceeded: Callable
    ):
        self.profile_id = profile_id
        self.context = context
        self.threshold_mb = threshold_mb
        self.on_threshold_exceeded = on_threshold_exceeded

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
                    self.on_threshold_exceeded()
                    break

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
                await asyncio.sleep(30)

    async def _get_memory_usage(self) -> int:
        """Get memory usage in MB"""
        try:
            # Get browser process
            pages = self.context.pages
            if not pages:
                return 0

            # Get CDP session
            page = pages[0]
            client = await page.context.new_cdp_session(page)

            # Get process info
            result = await client.send("SystemInfo.getProcessInfo")

            # Sum memory from all processes
            total_memory = 0
            for process in result.get("processInfo", []):
                total_memory += process.get("cpuTime", 0)

            # Fallback: use psutil
            if total_memory == 0:
                process = psutil.Process()
                total_memory = process.memory_info().rss

            return int(total_memory / (1024 * 1024))  # Convert to MB

        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return 0

    async def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage"""
        try:
            process = psutil.Process()
            return process.cpu_percent(interval=1)
        except:
            return 0.0

    def get_metrics(self) -> dict:
        """Get current metrics"""
        return {
            "memory_mb": self.current_memory_mb,
            "memory_limit_mb": self.threshold_mb,
            "cpu_percent": self.cpu_percent,
        }
