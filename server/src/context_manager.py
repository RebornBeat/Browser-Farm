import asyncio
import uuid
import logging
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from .models import Profile, ProfileStatus, ProxyConfig
from .script_runner import ScriptRunner
from .memory_monitor import MemoryMonitor

logger = logging.getLogger(__name__)


class ContextManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.browser: Optional[Browser] = None
        self.playwright = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.runners: Dict[str, ScriptRunner] = {}
        self.monitors: Dict[str, MemoryMonitor] = {}
        self.proxies: Dict[str, ProxyConfig] = {}

        # Create directories
        (self.data_dir / "screenshots").mkdir(exist_ok=True)
        (self.data_dir / "videos").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)

    async def start(self):
        """Start browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Headful for real rendering
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        logger.info("✓ Chromium launched")

    async def stop(self):
        """Stop browser and all contexts"""
        for profile_id in list(self.contexts.keys()):
            await self.stop_profile(profile_id)

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("Browser stopped")

    def register_proxy(self, proxy: ProxyConfig):
        """Register a proxy for use"""
        self.proxies[proxy.id] = proxy

    async def create_profile(self, profile: Profile, accounts: Dict[str, dict]):
        """Create and start a new browser context profile"""
        if profile.id in self.contexts:
            raise ValueError(f"Profile {profile.id} already exists")

        # Get proxy
        if profile.proxy_id not in self.proxies:
            raise ValueError(f"Proxy {profile.proxy_id} not found")
        proxy = self.proxies[profile.proxy_id]

        # Create context
        context = await self.browser.new_context(
            proxy={
                "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}",
                "username": proxy.username,
                "password": proxy.password,
            } if proxy.username else {
                "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}",
            },
            user_agent=profile.user_agent,
            locale=profile.locale,
            timezone_id=profile.timezone,
            geolocation={"latitude": profile.geolocation.lat, "longitude": profile.geolocation.lng} if profile.geolocation else None,
            permissions=["geolocation"] if profile.geolocation else [],
            record_video_dir=str(self.data_dir / "videos" / profile.id) if True else None,
            record_video_size={"width": 1920, "height": 1080},
        )

        self.contexts[profile.id] = context

        # Create script runner
        runner = ScriptRunner(
            profile_id=profile.id,
            context=context,
            script_code=profile.script_code,
            accounts=accounts,
            log_dir=self.data_dir / "logs" / profile.id
        )
        self.runners[profile.id] = runner

        # Create memory monitor
        monitor = MemoryMonitor(
            profile_id=profile.id,
            context=context,
            threshold_mb=profile.memory_threshold_mb,
            on_threshold_exceeded=lambda: asyncio.create_task(self.restart_profile(profile.id, profile, accounts))
        )
        self.monitors[profile.id] = monitor

        logger.info(f"Created profile {profile.id}")

        return profile.id

    async def start_profile(self, profile_id: str):
        """Start running the profile's script"""
        if profile_id not in self.runners:
            raise ValueError(f"Profile {profile_id} not found")

        runner = self.runners[profile_id]
        await runner.start()

        monitor = self.monitors[profile_id]
        monitor.start()

        logger.info(f"Started profile {profile_id}")

    async def pause_profile(self, profile_id: str):
        """Pause the profile's script"""
        if profile_id not in self.runners:
            raise ValueError(f"Profile {profile_id} not found")

        runner = self.runners[profile_id]
        await runner.pause()

        logger.info(f"Paused profile {profile_id}")

    async def stop_profile(self, profile_id: str):
        """Stop and remove a profile"""
        if profile_id not in self.contexts:
            raise ValueError(f"Profile {profile_id} not found")

        # Stop runner
        if profile_id in self.runners:
            await self.runners[profile_id].stop()
            del self.runners[profile_id]

        # Stop monitor
        if profile_id in self.monitors:
            self.monitors[profile_id].stop()
            del self.monitors[profile_id]

        # Close context
        context = self.contexts[profile_id]
        await context.close()
        del self.contexts[profile_id]

        logger.info(f"Stopped profile {profile_id}")

    async def restart_profile(self, profile_id: str, profile: Profile, accounts: Dict[str, dict]):
        """Restart a profile"""
        logger.info(f"Restarting profile {profile_id}...")

        # Stop
        await self.stop_profile(profile_id)

        # Start again
        await self.create_profile(profile, accounts)
        await self.start_profile(profile_id)

        logger.info(f"Profile {profile_id} restarted")

    async def get_screenshot(self, profile_id: str) -> bytes:
        """Take screenshot of profile"""
        if profile_id not in self.contexts:
            raise ValueError(f"Profile {profile_id} not found")

        context = self.contexts[profile_id]
        pages = context.pages

        if not pages:
            raise ValueError("No pages open in context")

        page = pages[0]
        screenshot = await page.screenshot(full_page=False)

        return screenshot

    async def save_screenshot(self, profile_id: str) -> str:
        """Save screenshot to disk"""
        screenshot = await self.get_screenshot(profile_id)

        timestamp = int(asyncio.get_event_loop().time())
        filename = f"{profile_id}_{timestamp}.png"
        filepath = self.data_dir / "screenshots" / filename

        with open(filepath, "wb") as f:
            f.write(screenshot)

        return filename

    def get_profile_status(self, profile_id: str) -> ProfileStatus:
        """Get current status of profile"""
        if profile_id not in self.runners:
            return ProfileStatus.STOPPED

        runner = self.runners[profile_id]
        return runner.status

    def get_profile_metrics(self, profile_id: str) -> dict:
        """Get metrics for profile"""
        if profile_id not in self.monitors:
            return {}

        monitor = self.monitors[profile_id]
        return monitor.get_metrics()
