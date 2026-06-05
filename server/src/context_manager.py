import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Dict, Optional, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from .models import Profile, ProfileStatus, ProxyConfig, ProfileMode
from .script_runner import ScriptRunner
from .memory_monitor import MemoryMonitor
from .xvfb_manager import XvfbManager

logger = logging.getLogger(__name__)


class ContextManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Main Playwright instance (Singleton)
        self.playwright: Optional[Playwright] = None

        # Resource Pools
        # We manage a dictionary of browsers because each profile gets its own process
        # bound to its own Xvfb display. This allows concurrent PyAutoGUI usage.
        self.browsers: Dict[str, Browser] = {}
        self.contexts: Dict[str, BrowserContext] = {}
        self.runners: Dict[str, ScriptRunner] = {}
        self.monitors: Dict[str, MemoryMonitor] = {}
        self.proxies: Dict[str, ProxyConfig] = {}

        # Xvfb Manager handles virtual displays for isolation
        # Initialized here, lifecycle managed by Server startup/shutdown
        self.xvfb_manager = XvfbManager()

        # Ensure data directories exist
        (self.data_dir / "screenshots").mkdir(exist_ok=True)
        (self.data_dir / "videos").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)

    async def start(self):
        """Initialize the Playwright engine."""
        try:
            self.playwright = await async_playwright().start()
            logger.info("✓ Playwright engine started")
        except Exception as e:
            logger.critical(f"Failed to start Playwright: {e}")
            raise

    async def stop(self):
        """Gracefully shutdown all active profiles and the Playwright engine."""
        logger.info("Initiating graceful shutdown...")

        # Stop all active profiles
        active_ids = list(self.contexts.keys())
        if active_ids:
            logger.info(f"Stopping {len(active_ids)} active profiles...")
            # Gather all stop coroutines to run concurrently
            await asyncio.gather(*[self.stop_profile(pid) for pid in active_ids])

        # Stop Playwright
        if self.playwright:
            await self.playwright.stop()
            logger.info("✓ Playwright engine stopped")

    def register_proxy(self, proxy: ProxyConfig):
        """Register a proxy configuration in the local pool."""
        self.proxies[proxy.id] = proxy
        logger.debug(f"Registered proxy: {proxy.id}")

    async def create_profile(self, profile: Profile, accounts: Dict[str, dict]):
        """
        Create a fully isolated browser profile environment.

        Workflow:
        1. Allocate a dedicated Xvfb display (Async).
        2. Launch a dedicated Chromium process bound to that display (with Timeout).
        3. Create a Browser Context with Proxy (Optional) & Geolocation settings.
        4. Inject Stealth Scripts to mask automation signatures.
        5. Initialize Script Runner and Resource Monitors.
        """
        if profile.id in self.contexts:
            raise ValueError(f"Profile {profile.id} already exists")

        # --- 1. Resource Allocation: Async Xvfb Display ---
        try:
            # FIX: Await the async Xvfb manager
            display_str = await self.xvfb_manager.start_display(profile.id)
            logger.info(f"[{profile.id}] Allocated Display: {display_str}")
        except Exception as e:
            logger.error(f"[{profile.id}] Failed to start Xvfb display: {e}")
            raise RuntimeError("Failed to allocate virtual display")

        # --- 2. Process Launch: Dedicated Browser ---
        browser: Optional[Browser] = None
        browser_pid: Optional[int] = None

        try:
            # --- UPDATE: Optional Proxy Logic ---
            proxy_config = None
            if profile.proxy_id:
                # User selected a specific proxy
                if profile.proxy_id in self.proxies:
                    p = self.proxies[profile.proxy_id]
                    proxy_config = {
                        "server": f"{p.protocol}://{p.host}:{p.port}",
                        "username": p.username,
                        "password": p.password,
                    }
                    logger.info(f"[{profile.id}] Using proxy: {p.host}:{p.port}")
                else:
                    # Proxy ID provided but not found in registry
                    logger.warning(f"[{profile.id}] Proxy ID {profile.proxy_id} not found. Proceeding without proxy.")
            else:
                # No proxy selected (None)
                logger.info(f"[{profile.id}] No proxy selected. Running direct connection.")

            # Launch Browser Instance with Timeout
            # FIX: Wrapped in wait_for to prevent indefinite hangs
            try:
                browser = await asyncio.wait_for(
                    self.playwright.chromium.launch(
                        headless=False,  # Must be headful for Xvfb/PyAutoGUI rendering
                        proxy=proxy_config, # Playwright handles None correctly (Direct connection)
                        args=[
                            "--disable-blink-features=AutomationControlled",  # Mask Chrome automation flags
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",  # Often helpful in Xvfb
                            "--disable-infobars",
                            "--start-maximized",
                        ],
                        env={"DISPLAY": display_str} # Critical: Bind browser to specific display
                    ),
                    timeout=60.0 # 60 second hard timeout for launch
                )
            except asyncio.TimeoutError:
                logger.error(f"[{profile.id}] Browser launch timed out after 60s.")
                raise RuntimeError("Browser launch timed out")

            self.browsers[profile.id] = browser

            # --- CRITICAL FIX: PID Extraction ---
            # Python Playwright 'Browser' object does NOT expose .process() like Node.js.
            # We cannot get the PID directly for accurate monitoring.
            # We pass None, and the MemoryMonitor will fallback to CDP metrics.
            # browser_pid remains None (initialized above)
            logger.info(f"[{profile.id}] Browser launched successfully (Python API does not expose PID).")

        except Exception as e:
            logger.error(f"[{profile.id}] Browser launch failed: {e}")
            # FIX: Await cleanup of Xvfb
            await self.xvfb_manager.stop_display(profile.id)
            raise RuntimeError(f"Browser launch failed: {e}")

        # --- 3. Context Creation & Stealth Injection ---
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=profile.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                locale=profile.locale,
                timezone_id=profile.timezone,
                geolocation={"latitude": profile.geolocation.lat, "longitude": profile.geolocation.lng} if profile.geolocation else None,
                permissions=["geolocation"] if profile.geolocation else [],
                ignore_https_errors=True,
                # Record video for debugging
                record_video_dir=str(self.data_dir / "videos" / profile.id),
                record_video_size={"width": 1920, "height": 1080}
            )
            self.contexts[profile.id] = context

            # --- ADVANCED STEALTH INJECTION ---
            # Inject script to run before any page content loads to mask webdriver flags
            await context.add_init_script("""
                // Overwrite navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Fake plugins array
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ]
                });

                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Mock Chrome runtime object
                window.chrome = { runtime: {} };
            """)

            # Create a default page immediately so PyAutoGUI has a window to target
            # This ensures the browser window is "realized" on the Xvfb display
            page = await context.new_page()
            logger.info(f"[{profile.id}] Context created with Stealth Injection")

        except Exception as e:
            logger.error(f"[{profile.id}] Context creation failed: {e}")
            if browser: await browser.close()
            del self.browsers[profile.id]
            # FIX: Await cleanup
            await self.xvfb_manager.stop_display(profile.id)
            raise

        # --- 4. Logic Initialization: Runner & Monitor ---

        # Script Runner
        runner = ScriptRunner(
            profile_id=profile.id,
            context=context,
            mode=profile.mode,
            scripts=profile.scripts,
            requirements=profile.requirements,
            accounts=accounts,
            display_env=display_str,
            log_dir=self.data_dir / "logs" / profile.id
        )
        self.runners[profile.id] = runner

        # Memory Monitor (Now passing browser_pid for accurate tracking)
        monitor = MemoryMonitor(
            profile_id=profile.id,
            context=context,
            threshold_mb=profile.memory_threshold_mb,
            on_threshold_exceeded=lambda: asyncio.create_task(
                self.restart_profile(profile.id, profile, accounts)
            ),
            browser_pid=browser_pid # Pass the PID here (None in Python)
        )
        self.monitors[profile.id] = monitor

        logger.info(f"✓ Profile {profile.id} initialized successfully")
        return profile.id

    async def start_profile(self, profile_id: str):
        """Start the script execution loop for a profile."""
        if profile_id not in self.runners:
            raise ValueError(f"Profile {profile_id} not found")

        runner = self.runners[profile_id]
        monitor = self.monitors[profile_id]

        # Start monitoring
        monitor.start()

        # Start script execution
        await runner.start()

        logger.info(f"▶ Profile {profile_id} started")

    async def pause_profile(self, profile_id: str):
        """Pause the script execution."""
        if profile_id not in self.runners:
            raise ValueError(f"Profile {profile_id} not found")

        await self.runners[profile_id].pause()
        logger.info(f"⏸ Profile {profile_id} paused")

    async def stop_profile(self, profile_id: str):
        """Stop script, close browser, and release Xvfb display."""
        logger.info(f"Stopping profile {profile_id}...")

        # 1. Stop Script Runner
        if profile_id in self.runners:
            try:
                await self.runners[profile_id].stop()
            except Exception as e:
                logger.error(f"Error stopping runner {profile_id}: {e}")
            del self.runners[profile_id]

        # 2. Stop Monitor
        if profile_id in self.monitors:
            self.monitors[profile_id].stop()
            del self.monitors[profile_id]

        # 3. Close Browser Context
        if profile_id in self.contexts:
            try:
                await self.contexts[profile_id].close()
            except Exception as e:
                logger.error(f"Error closing context {profile_id}: {e}")
            del self.contexts[profile_id]

        # 4. Close Browser Process
        if profile_id in self.browsers:
            try:
                await self.browsers[profile_id].close()
            except Exception as e:
                logger.error(f"Error closing browser {profile_id}: {e}")
            del self.browsers[profile_id]

        # 5. Release Xvfb Display
        # FIX: Await the async stop_display method
        await self.xvfb_manager.stop_display(profile_id)

        logger.info(f"⏹ Profile {profile_id} stopped and resources released")

    async def restart_profile(self, profile_id: str, profile: Profile, accounts: Dict[str, dict]):
        """Handle automatic restart logic (e.g., after memory threshold breach)."""
        logger.warning(f"⚠ Profile {profile_id} triggered restart. Re-initializing...")

        await self.stop_profile(profile_id)

        # Small delay to ensure resources are fully released
        await asyncio.sleep(2)

        await self.create_profile(profile, accounts)
        await self.start_profile(profile_id)

        logger.info(f"✓ Profile {profile_id} restarted successfully")

    # --- Helper Methods ---

    async def get_screenshot(self, profile_id: str) -> bytes:
        """Capture a screenshot of the active page."""
        if profile_id not in self.contexts:
            raise ValueError(f"Profile {profile_id} not found")

        context = self.contexts[profile_id]
        pages = context.pages

        if not pages:
            # If no page is open, return a placeholder or raise error
            raise ValueError("No pages open in context")

        # Capture from the active page (usually the last one)
        page = pages[-1]
        return await page.screenshot(type="png")

    async def save_screenshot(self, profile_id: str) -> str:
        """Save a screenshot to disk and return filename."""
        screenshot = await self.get_screenshot(profile_id)

        timestamp = int(asyncio.get_event_loop().time())
        filename = f"{profile_id}_{timestamp}.png"
        filepath = self.data_dir / "screenshots" / filename

        with open(filepath, "wb") as f:
            f.write(screenshot)

        return filename

    def get_profile_status(self, profile_id: str) -> ProfileStatus:
        """Get the current operational status of a profile."""
        if profile_id not in self.runners:
            return ProfileStatus.STOPPED
        return self.runners[profile_id].status

    def get_profile_metrics(self, profile_id: str) -> dict:
        """Retrieve resource metrics for a profile."""
        if profile_id not in self.monitors:
            return {}
        return self.monitors[profile_id].get_metrics()
