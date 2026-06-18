import asyncio
import logging
import subprocess
import sys
import os
import aiohttp
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import BrowserContext
from .models import ProfileStatus, ProfileMode

logger = logging.getLogger(__name__)


# --- Shared State Helpers (Communicate with Local Server API) ---

async def _get_shared_state(key: str):
    """Helper to get state from the server's internal key-value store."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:8080/state/{key}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
    except Exception as e:
        logger.error(f"Failed to get shared state: {e}")
        return {}

async def _set_shared_state(key: str, value: dict):
    """Helper to set state in the server's internal key-value store."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://localhost:8080/state/{key}", json=value) as resp:
                return await resp.json()
    except Exception as e:
        logger.error(f"Failed to set shared state: {e}")
        return {"error": str(e)}


def _create_get_account_function(accounts: Dict[str, dict]):
    """
    Creates a closure for the get_account function bound to a specific
    set of accounts. This ensures thread-safety for concurrent profiles.
    """
    def get_account(account_id: str) -> dict:
        if account_id not in accounts:
            raise ValueError(f"Account {account_id} not found")
        return accounts[account_id]
    return get_account


class ScriptRunner:
    def __init__(
        self,
        profile_id: str,
        context: BrowserContext,
        mode: ProfileMode,
        scripts: List[str],
        requirements: List[str],
        accounts: Dict[str, dict],
        display_env: str,
        log_dir: Path,
        input_controller=None  # NEW: System-level input
    ):
        self.profile_id = profile_id
        self.context = context
        self.mode = mode
        self.scripts = scripts
        self.requirements = requirements
        self.accounts = accounts
        self.display_env = display_env
        self.log_dir = log_dir
        self.input_controller = input_controller  # NEW
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.task: Optional[asyncio.Task] = None
        self.status = ProfileStatus.IDLE

        # Set up logging
        self.log_file = self.log_dir / "script.log"
        self.setup_logging()

    def setup_logging(self):
        """Set up logging for this script"""
        # Clear existing handlers to prevent duplicates on restarts
        script_logger = logging.getLogger(f"script.{self.profile_id}")
        if script_logger.hasHandlers():
            script_logger.handlers.clear()

        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        script_logger.addHandler(file_handler)
        script_logger.setLevel(logging.INFO)

    async def install_dependencies(self):
        """Install pip requirements for this profile."""
        if not self.requirements:
            return

        logger.info(f"[{self.profile_id}] Installing dependencies: {self.requirements}")
        script_logger = logging.getLogger(f"script.{self.profile_id}")
        script_logger.info(f"Installing requirements: {self.requirements}")

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", *self.requirements,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"[{self.profile_id}] Dependencies installed successfully.")
                script_logger.info("Dependencies installed successfully.")
            else:
                err_msg = stderr.decode()
                logger.error(f"[{self.profile_id}] Pip install failed: {err_msg}")
                script_logger.error(f"Dependency installation failed: {err_msg}")
                raise Exception(f"Failed to install dependencies: {err_msg}")

        except Exception as e:
            logger.error(f"[{self.profile_id}] Exception during dependency install: {e}")
            raise

    async def start(self):
        """Start running the script"""
        if self.task and not self.task.done():
            logger.warning(f"Script {self.profile_id} already running")
            return

        # Pre-flight: Install Dependencies if present
        if self.requirements:
            self.status = ProfileStatus.INSTALLING
            try:
                await self.install_dependencies()
            except Exception:
                self.status = ProfileStatus.CRASHED
                return

        self.status = ProfileStatus.RUNNING
        self.task = asyncio.create_task(self._run())
        logger.info(f"Started script {self.profile_id} in {self.mode} mode")

    async def pause(self):
        """Pause the script"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.status = ProfileStatus.PAUSED
        logger.info(f"Paused script {self.profile_id}")

    async def stop(self):
        """Stop the script"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.status = ProfileStatus.STOPPED
        logger.info(f"Stopped script {self.profile_id}")

    async def _run(self):
        """Run the user's script based on the profile mode."""
        script_logger = logging.getLogger(f"script.{self.profile_id}")

        try:
            # Set the DISPLAY environment variable for this specific task
            # Critical for PyAutoGUI to target the correct Xvfb display
            os.environ["DISPLAY"] = self.display_env

            # --- MODE: MANUAL ---
            if self.mode == ProfileMode.MANUAL:
                script_logger.info("Profile running in MANUAL mode. Browser active, no script execution.")
                self.status = ProfileStatus.RUNNING
                # Keep the context alive indefinitely until cancelled
                while True:
                    await asyncio.sleep(3600)

            # --- MODE: AUTOMATED / COMMAND CENTER ---
            script_logger.info(f"Profile running in {self.mode} mode. Executing {len(self.scripts)} script(s).")

            # Prepare injected functions
            injected_get_account = _create_get_account_function(self.accounts)

            # Prepare external libraries for injection
            # We initialize as None, then attempt import.
            # This prevents NameError if requirements were not set but script doesn't use them.
            _pyautogui = None
            _BeautifulSoup = None

            try:
                import pyautogui
                _pyautogui = pyautogui
            except ImportError:
                pass # User script might not need it

            try:
                from bs4 import BeautifulSoup
                _BeautifulSoup = BeautifulSoup
            except ImportError:
                pass

            # Execute Script Chain
            for i, script_code in enumerate(self.scripts):
                if self.status == ProfileStatus.STOPPED:
                    break

                script_logger.info(f"Executing script module {i+1}/{len(self.scripts)}...")

                # Prepare Namespace
                namespace = {
                    # Context & Page
                    "context": self.context,
                    "page": self.context.pages[0] if self.context.pages else None,

                    # Data Access
                    "accounts": self.accounts,
                    "get_account": injected_get_account,

                    # Shared State API
                    "get_state": _get_shared_state,
                    "set_state": _set_shared_state,

                    # External Libraries (Injected)
                    "pyautogui": _pyautogui,
                    "BeautifulSoup": _BeautifulSoup,

                    # NEW: Human-like helpers
                    "human_type": human_type,
                    "human_move": human_move,

                    # NEW: System input controller (for advanced scripts)
                    "input": self.input_controller,

                    # Standard Libs
                    "asyncio": asyncio,
                    "os": os,
                    "random": __import__("random"),
                    "__name__": "__main__",
                }

                # Execute Script Code
                exec(script_code, namespace)

                # If the script defines a main() function, run it
                if "main" in namespace and callable(namespace["main"]):
                    await namespace["main"](self.context)

                script_logger.info(f"Script module {i+1} finished.")

            script_logger.info("All scripts executed successfully.")
            self.status = ProfileStatus.IDLE

        except asyncio.CancelledError:
            script_logger.info("Script cancelled")
            self.status = ProfileStatus.STOPPED
            raise
        except Exception as e:
            script_logger.error(f"Script error: {e}", exc_info=True)
            self.status = ProfileStatus.CRASHED
            raise

    # Prepare human_type helper
    async def human_type(text: str, element=None, min_delay: float = 0.05, max_delay: float = 0.15, mistake_rate: float = 0.02):
        """
        Type text with human-like delays and occasional mistakes.

        Args:
            text: Text to type
            element: Optional Playwright element to type into
            min_delay: Minimum delay between keystrokes (seconds)
            max_delay: Maximum delay between keystrokes (seconds)
            mistake_rate: Probability of typing a wrong character (0.0-1.0)
        """
        import random as _r
        for char in text:
            # Random mistake
            if _r.random() < mistake_rate:
                wrong_char = _r.choice("abcdefghijklmnopqrstuvwxyz")
                if element:
                    await element.type(wrong_char, delay=int(_r.uniform(min_delay, max_delay) * 1000))
                else:
                    await self.context.pages[0].keyboard.type(wrong_char)
                await asyncio.sleep(_r.uniform(0.1, 0.3))
                # Backspace
                if element:
                    await element.press("Backspace")
                else:
                    await self.context.pages[0].keyboard.press("Backspace")
                await asyncio.sleep(_r.uniform(0.1, 0.2))

            # Type correct character
            if element:
                await element.type(char, delay=int(_r.uniform(min_delay, max_delay) * 1000))
            else:
                await self.context.pages[0].keyboard.type(char)
            await asyncio.sleep(_r.uniform(min_delay, max_delay))

    # Prepare human_move helper (uses system input if available)
    async def human_move(x: int, y: int, duration: float = 1.0):
        """
        Move mouse to coordinates with human-like curve.
        Uses system-level input (xdotool) if available, falls back to Playwright.
        """
        import random as _r
        if self.input_controller:
            # Use system input with intermediate points for curve
            current_steps = max(int(duration * 60), 10)  # 60 FPS
            # Generate Bezier-like path
            for i in range(current_steps):
                progress = i / current_steps
                # Ease-in-out
                eased = progress * progress * (3 - 2 * progress)
                intermediate_x = int(x * eased + _r.uniform(-2, 2))
                intermediate_y = int(y * eased + _r.uniform(-2, 2))
                await self.input_controller.mouse_move(intermediate_x, intermediate_y)
                await asyncio.sleep(duration / current_steps)
            # Final position
            await self.input_controller.mouse_move(x, y)
        else:
            # Fallback to Playwright
            page = self.context.pages[0] if self.context.pages else None
            if page:
                await page.mouse.move(x, y, steps=int(duration * 50))
