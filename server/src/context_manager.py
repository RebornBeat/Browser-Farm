import asyncio
import logging
import os
import json
import io
import random
from pathlib import Path
from typing import Dict, Optional, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from PIL import Image, ImageDraw
from .models import Profile, ProfileStatus, ProxyConfig, ProfileMode
from .script_runner import ScriptRunner
from .memory_monitor import MemoryMonitor
from .xvfb_manager import XvfbManager
from .video_recorder import VideoRecorder
from .input_controller import InputController

logger = logging.getLogger(__name__)

# NEW: List of high-target sites for random startup
STARTUP_SITES = [
    "https://www.google.com",
    "https://www.youtube.com",
    "https://x.com",
    "https://www.amazon.com",
    "https://www.wikipedia.org",
    "https://www.linkedin.com",
    "https://www.instagram.com",
    "https://www.twitch.tv",
    "https://www.duckduckgo.com",
    "https://www.bing.com",
    "https://news.ycombinator.com",
    "https://github.com",
    "https://www.netflix.com",
    "https://www.spotify.com"
]


class ContextManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Main Playwright instance (Singleton)
        self.playwright: Optional[Playwright] = None

        # Resource Pools
        # NOTE: With persistent_context, we don't have separate Browser objects.
        # The context IS the browser. We track contexts directly.
        self.contexts: Dict[str, BrowserContext] = {}
        self.runners: Dict[str, ScriptRunner] = {}
        self.monitors: Dict[str, MemoryMonitor] = {}
        self.proxies: Dict[str, ProxyConfig] = {}
        self.recorders: Dict[str, VideoRecorder] = {}
        self.input_controllers: Dict[str, InputController] = {}
        self.profile_data_dirs: Dict[str, Path] = {}

        # Xvfb Manager
        self.xvfb_manager = XvfbManager()

        # Ensure data directories exist
        (self.data_dir / "screenshots").mkdir(exist_ok=True)
        # Videos are now per-profile, created on demand
        (self.data_dir / "profiles").mkdir(exist_ok=True)
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

        active_ids = list(self.contexts.keys())
        if active_ids:
            logger.info(f"Stopping {len(active_ids)} active profiles...")
            await asyncio.gather(*[self.stop_profile(pid) for pid in active_ids])

        if self.playwright:
            await self.playwright.stop()
            logger.info("✓ Playwright engine stopped")

    def register_proxy(self, proxy: ProxyConfig):
        """Register a proxy configuration in the local pool."""
        self.proxies[proxy.id] = proxy
        logger.debug(f"Registered proxy: {proxy.id}")

    def _get_browser_launch_args(self, profile: Profile) -> list:
        """
        Generate browser launch args based on engine type and profile config.
        """
        locale = profile.locale or "en-US"
        locale_short = locale.split("-")[0] if "-" in locale else locale

        if profile.browser_engine == "chrome":
            # Genuine Chrome path - fewer flags needed
            args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-position=0,0",
                "--window-size=1920,1080",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-default-apps",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-popup-blocking",
                "--metrics-recording-only",
                "--mute-audio",
                f"--lang={locale}",
                f"--accept-lang={locale},{locale_short};q=0.9",
            ]

            # GPU handling for Chrome path
            # If running in Xvfb without GPU, we must disable GPU
            # But we spoof WebGL via JS to compensate
            args.append("--disable-gpu")
            args.append("--disable-software-rasterizer")

            return args

        else:
            # Chromium path - comprehensive flags
            args = [
                # Anti-detection
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process,AutomationControlled",

                # Stability in Xvfb
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",

                # Window management
                "--window-position=0,0",
                "--window-size=1920,1080",
                "--start-maximized",

                # Suppress automation signals
                "--disable-infobars",
                "--disable-extensions",
                "--disable-default-apps",
                "--disable-component-extensions-with-background-pages",
                "--disable-component-update",
                "--disable-background-networking",
                "--disable-client-side-phishing-detection",
                "--disable-domain-reliability",
                "--disable-sync",
                "--disable-translate",
                "--disable-features=TranslateUI",

                # First-run suppression
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pings",

                # Credential storage
                "--password-store=basic",
                "--use-mock-keychain",

                # Misc
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-popup-blocking",
                "--metrics-recording-only",
                "--mute-audio",
                "--autoplay-policy=no-user-gesture-required",

                # Locale
                f"--lang={locale}",
                f"--accept-lang={locale},{locale_short};q=0.9",
            ]

            return args

    def _build_stealth_config(self, profile: Profile) -> dict:
        """
        Build the configuration dict for the stealth injection script.
        Maps profile settings to JS-injectable values.
        """
        locale = profile.locale or "en-US"
        locale_short = locale.split("-")[0] if "-" in locale else locale

        # Default GPU strings based on OS fingerprint
        gpu_defaults = {
            "windows": {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
            },
            "macos": {
                "vendor": "Google Inc. (Apple)",
                "renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1)"
            },
            "linux": {
                "vendor": "Google Inc. (Intel)",
                "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 (CFL GT2) OpenGL ES 3.2)"
            }
        }

        os_defaults = gpu_defaults.get(profile.os_fingerprint, gpu_defaults["windows"])

        platform_map = {
            "windows": "Win32",
            "macos": "MacIntel",
            "linux": "Linux x86_64"
        }

        return {
            "languages": [locale, locale_short],
            "hardware_concurrency": profile.hardware_concurrency,
            "device_memory": profile.device_memory,
            "platform": platform_map.get(profile.os_fingerprint, "Win32"),
            "gpu_vendor": profile.gpu_vendor or os_defaults["vendor"],
            "gpu_renderer": profile.gpu_renderer or os_defaults["renderer"],
            "os_fingerprint": profile.os_fingerprint,
        }

    def _get_chrome_executable(self) -> Optional[str]:
        """
        Find the Google Chrome executable on the system.
        Returns None if not found (will fall back to Chromium).
        """
        import shutil
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/opt/google/chrome/chrome",
        ]
        for path in possible_paths:
            if shutil.which(path) or Path(path).exists():
                return path
        return None

    async def create_profile(self, profile: Profile, accounts: Dict[str, dict]):
        """
        Create a fully isolated, persistent browser profile environment.

        Workflow:
        1. Allocate Xvfb display
        2. Create persistent user data directory
        3. Launch persistent context (Chromium or Chrome)
        4. Inject stealth scripts
        5. Initialize InputController, VideoRecorder, ScriptRunner, MemoryMonitor
        """
        if profile.id in self.contexts:
            raise ValueError(f"Profile {profile.id} already exists")

        # --- 1. Xvfb Display Allocation ---
        try:
            display_str = await self.xvfb_manager.start_display(profile.id)
            logger.info(f"[{profile.id}] Allocated Display: {display_str}")
        except Exception as e:
            logger.error(f"[{profile.id}] Failed to start Xvfb display: {e}")
            raise RuntimeError("Failed to allocate virtual display")

        # --- 2. Persistent User Data Directory ---
        profile_data_dir = self.data_dir / "profiles" / profile.id
        user_data_dir = profile_data_dir / "browser_data"
        video_dir = profile_data_dir / "videos"
        log_dir = profile_data_dir / "logs"

        user_data_dir.mkdir(parents=True, exist_ok=True)
        video_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        self.profile_data_dirs[profile.id] = profile_data_dir

        # --- 3. Proxy Configuration ---
        proxy_config = None
        if profile.proxy_id and profile.proxy_id in self.proxies:
            p = self.proxies[profile.proxy_id]
            proxy_config = {
                "server": f"{p.protocol}://{p.host}:{p.port}",
                "username": p.username,
                "password": p.password,
            }
            logger.info(f"[{profile.id}] Using proxy: {p.host}:{p.port}")
        else:
            logger.info(f"[{profile.id}] No proxy selected. Direct connection.")

        # --- 4. Browser Launch Args ---
        launch_args = self._get_browser_launch_args(profile)

        # --- 5. Stealth Config ---
        stealth_config = self._build_stealth_config(profile)

        # --- 6. User Agent ---
        # If not provided, use a modern Chrome UA matching the engine
        if not profile.user_agent:
            if profile.os_fingerprint == "windows":
                profile.user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                )
            elif profile.os_fingerprint == "macos":
                profile.user_agent = (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                )
            else:
                profile.user_agent = (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                )

        # --- 7. Client Hints Headers ---
        extra_headers = {
            "sec-ch-ua": '"Google Chrome";v="130", "Chromium";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{profile.os_fingerprint.capitalize()}"',
        }

        # --- 8. Launch Persistent Context ---
        context: Optional[BrowserContext] = None

        try:
            # Determine executable path for Chrome engine
            executable_path = None
            channel = None

            if profile.browser_engine == "chrome":
                executable_path = self._get_chrome_executable()
                if not executable_path:
                    logger.warning(
                        f"[{profile.id}] Chrome not found, falling back to Chromium. "
                        f"Install with: sudo apt install google-chrome-stable"
                    )
                    # Fall back to Chromium
                    profile.browser_engine = "chromium"
                else:
                    logger.info(f"[{profile.id}] Using Genuine Chrome: {executable_path}")

            # Build launch parameters
            launch_params = {
                "user_data_dir": str(user_data_dir),
                "headless": False,  # Must be headful for Xvfb/PyAutoGUI
                "proxy": proxy_config,
                "args": launch_args,
                "env": {"DISPLAY": display_str},
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": profile.user_agent,
                "locale": profile.locale,
                "timezone_id": profile.timezone,
                "geolocation": (
                    {"latitude": profile.geolocation.lat, "longitude": profile.geolocation.lng}
                    if profile.geolocation else None
                ),
                "permissions": (["geolocation"] if profile.geolocation else []),
                "ignore_https_errors": True,
                "extra_http_headers": extra_headers,
                "java_script_enabled": True,
                # NO record_video_dir - we use FFmpeg now
                # NO record_video_size
            }

            if executable_path:
                launch_params["executable_path"] = executable_path

            # Launch with timeout
            context = await asyncio.wait_for(
                self.playwright.chromium.launch_persistent_context(**launch_params),
                timeout=90.0  # Persistent context may take longer (first-run setup)
            )

            self.contexts[profile.id] = context
            logger.info(f"[{profile.id}] Persistent context launched ({profile.browser_engine})")

        except asyncio.TimeoutError:
            logger.error(f"[{profile.id}] Browser launch timed out after 90s")
            await self.xvfb_manager.stop_display(profile.id)
            raise RuntimeError("Browser launch timed out")

        except Exception as e:
            logger.error(f"[{profile.id}] Browser launch failed: {e}")
            await self.xvfb_manager.stop_display(profile.id)
            raise RuntimeError(f"Browser launch failed: {e}")

        # --- 9. Stealth Injection ---
        try:
            from .stealth import generate_stealth_script

            stealth_js = generate_stealth_script(stealth_config)
            await context.add_init_script(stealth_js)
            logger.info(f"[{profile.id}] Stealth injection applied")

        except Exception as e:
            logger.error(f"[{profile.id}] Stealth injection failed: {e}")
            # Non-fatal, continue

        # --- 10. Create Default Page & Navigate ---
        try:
            page = await context.new_page()

            random_url = random.choice(STARTUP_SITES)
            logger.info(f"[{profile.id}] Navigating to random startup: {random_url}")

            try:
                await page.goto(random_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"[{profile.id}] Startup navigation failed: {e}")

        except Exception as e:
            logger.error(f"[{profile.id}] Page creation failed: {e}")
            await context.close()
            del self.contexts[profile.id]
            await self.xvfb_manager.stop_display(profile.id)
            raise

        # --- 11. Initialize InputController ---
        input_controller = InputController(display=display_str)
        self.input_controllers[profile.id] = input_controller
        logger.info(f"[{profile.id}] InputController initialized (display={display_str})")

        # --- 12. Initialize VideoRecorder ---
        recorder = VideoRecorder(
            display=display_str,
            output_dir=video_dir,
            resolution="1920x1080",
            framerate=30
        )
        self.recorders[profile.id] = recorder
        logger.info(f"[{profile.id}] VideoRecorder initialized")

        # --- 13. ScriptRunner ---
        runner = ScriptRunner(
            profile_id=profile.id,
            context=context,
            mode=profile.mode,
            scripts=profile.scripts,
            requirements=profile.requirements,
            accounts=accounts,
            display_env=display_str,
            log_dir=log_dir,
            input_controller=input_controller  # NEW: Pass input controller
        )
        self.runners[profile.id] = runner

        # --- 14. MemoryMonitor ---
        # Try to get browser PID for accurate monitoring
        # Persistent context may expose the process differently
        browser_pid = None
        try:
            # For persistent context, the browser process is the context's browser
            browser = context.browser
            if browser and hasattr(browser, '_impl_obj'):
                # Python Playwright doesn't expose PID directly
                # We'll find it via psutil by matching DISPLAY
                import psutil
                for proc in psutil.process_iter(['pid', 'environ', 'name']):
                    try:
                        env = proc.info.get('environ') or {}
                        if env.get('DISPLAY') == display_str and 'chrome' in (proc.info.get('name') or '').lower():
                            browser_pid = proc.info['pid']
                            break
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        continue
        except Exception:
            pass

        monitor = MemoryMonitor(
            profile_id=profile.id,
            context=context,
            threshold_mb=profile.memory_threshold_mb,
            on_threshold_exceeded=lambda: asyncio.create_task(
                self.restart_profile(profile.id, profile, accounts)
            ),
            browser_pid=browser_pid
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

        monitor.start()
        await runner.start()

        logger.info(f"▶ Profile {profile_id} started")

    async def pause_profile(self, profile_id: str):
        """Pause the script execution."""
        if profile_id not in self.runners:
            raise ValueError(f"Profile {profile_id} not found")

        await self.runners[profile_id].pause()
        logger.info(f"⏸ Profile {profile_id} paused")

    async def stop_profile(self, profile_id: str):
        """Stop script, close browser, release Xvfb display, stop recording."""
        logger.info(f"Stopping profile {profile_id}...")

        # 1. Stop Video Recorder
        if profile_id in self.recorders:
            try:
                await self.recorders[profile_id].stop()
            except Exception as e:
                logger.error(f"Error stopping recorder {profile_id}: {e}")
            # Keep recorder instance for status queries, just stop active recording

        # 2. Stop Script Runner
        if profile_id in self.runners:
            try:
                await self.runners[profile_id].stop()
            except Exception as e:
                logger.error(f"Error stopping runner {profile_id}: {e}")
            del self.runners[profile_id]

        # 3. Stop Monitor
        if profile_id in self.monitors:
            self.monitors[profile_id].stop()
            del self.monitors[profile_id]

        # 4. Close Context (this closes the browser for persistent_context)
        if profile_id in self.contexts:
            try:
                await self.contexts[profile_id].close()
            except Exception as e:
                logger.error(f"Error closing context {profile_id}: {e}")
            del self.contexts[profile_id]

        # 5. Cleanup InputController
        if profile_id in self.input_controllers:
            del self.input_controllers[profile_id]

        # 6. Release Xvfb Display
        await self.xvfb_manager.stop_display(profile_id)

        logger.info(f"⏹ Profile {profile_id} stopped and resources released")

    async def restart_profile(self, profile_id: str, profile: Profile, accounts: Dict[str, dict]):
        """Handle automatic restart logic."""
        logger.warning(f"⚠ Profile {profile_id} triggered restart. Re-initializing...")

        await self.stop_profile(profile_id)
        await asyncio.sleep(2)
        await self.create_profile(profile, accounts)
        await self.start_profile(profile_id)

        logger.info(f"✓ Profile {profile_id} restarted successfully")

    # --- Video Recording Methods ---

    async def start_recording(self, profile_id: str) -> str:
        """Start video recording for a profile."""
        if profile_id not in self.recorders:
            raise ValueError(f"Profile {profile_id} not found or not initialized")
        return await self.recorders[profile_id].start()

    async def stop_recording(self, profile_id: str) -> Optional[str]:
        """Stop video recording for a profile."""
        if profile_id not in self.recorders:
            raise ValueError(f"Profile {profile_id} not found")
        return await self.recorders[profile_id].stop()

    def get_recording_status(self, profile_id: str) -> dict:
        """Get recording status for a profile."""
        if profile_id not in self.recorders:
            return {"recording": False}
        status = self.recorders[profile_id].get_status()
        return {
            "recording": status.recording,
            "duration_seconds": status.duration_seconds,
            "file_size_bytes": status.file_size_bytes,
            "filename": status.filename,
        }

    def get_input_controller(self, profile_id: str) -> Optional[InputController]:
        """Get the InputController for a profile."""
        return self.input_controllers.get(profile_id)

    # --- Helper Methods ---

    async def get_screenshot(self, profile_id: str) -> bytes:
        """Capture a screenshot of the active page."""
        if profile_id not in self.contexts:
            raise ValueError(f"Profile {profile_id} not found")

        context = self.contexts[profile_id]
        pages = context.pages

        if not pages:
            logger.info(f"[{profile_id}] No pages open. Sending placeholder.")
            return self._generate_placeholder_image("Initializing...")

        page = pages[-1]
        return await page.screenshot(type="png")

    def _generate_placeholder_image(self, text: str) -> bytes:
        """Generates a placeholder image when browser is initializing."""
        width, height = 1920, 1080
        img = Image.new('RGB', (width, height), color=(15, 23, 42))
        d = ImageDraw.Draw(img)
        d.text((width / 2, height / 2), text, fill=(100, 116, 139), anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()

    async def save_screenshot(self, profile_id: str) -> str:
        """Save a screenshot to disk and return filename."""
        screenshot = await self.get_screenshot(profile_id)
        timestamp = int(asyncio.get_event_loop().time())
        filename = f"{profile_id}_{timestamp}.png"
        filepath = self.data_dir / "screenshots" / filename
        with open(filepath, "wb") as f:
            f.write(screenshot)
        return filename

    async def delete_screenshot(self, filename: str) -> bool:
        """Delete a screenshot file from disk."""
        filepath = self.data_dir / "screenshots" / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    async def delete_video(self, profile_id: str, filename: str) -> bool:
        """Delete a video file from disk."""
        if profile_id not in self.profile_data_dirs:
            return False
        video_dir = self.profile_data_dirs[profile_id] / "videos"
        filepath = video_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

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

    def get_current_url(self, profile_id: str) -> Optional[str]:
        """Returns the URL of the active page."""
        if profile_id not in self.contexts:
            return None
        pages = self.contexts[profile_id].pages
        if not pages:
            return None
        return pages[-1].url

    def get_profile_videos(self, profile_id: str) -> List[dict]:
        """List all videos for a profile."""
        if profile_id not in self.profile_data_dirs:
            return []
        video_dir = self.profile_data_dirs[profile_id] / "videos"
        if not video_dir.exists():
            return []
        files = sorted(video_dir.glob("*.mp4"), reverse=True)
        return [
            {
                "id": file.stem,
                "timestamp": file.stat().st_mtime,
                "url": f"/videos/{profile_id}/{file.name}",
                "size_bytes": file.stat().st_size,
                "filename": file.name,
            }
            for file in files
        ]
