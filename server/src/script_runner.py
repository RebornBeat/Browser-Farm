import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import BrowserContext
from .models import ProfileStatus

logger = logging.getLogger(__name__)


class ScriptRunner:
    def __init__(
        self,
        profile_id: str,
        context: BrowserContext,
        script_code: str,
        accounts: Dict[str, dict],
        log_dir: Path
    ):
        self.profile_id = profile_id
        self.context = context
        self.script_code = script_code
        self.accounts = accounts
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.task: Optional[asyncio.Task] = None
        self.status = ProfileStatus.IDLE

        # Set up logging
        self.log_file = self.log_dir / "script.log"
        self.setup_logging()

    def setup_logging(self):
        """Set up logging for this script"""
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        script_logger = logging.getLogger(f"script.{self.profile_id}")
        script_logger.addHandler(file_handler)
        script_logger.setLevel(logging.INFO)

    async def start(self):
        """Start running the script"""
        if self.task and not self.task.done():
            logger.warning(f"Script {self.profile_id} already running")
            return

        self.status = ProfileStatus.RUNNING
        self.task = asyncio.create_task(self._run())
        logger.info(f"Started script {self.profile_id}")

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
        """Run the user's script"""
        script_logger = logging.getLogger(f"script.{self.profile_id}")

        try:
            script_logger.info("Script started")

            # Prepare environment
            accounts_json = json.dumps(self.accounts)
            os.environ["BROWSER_FARM_ACCOUNTS"] = accounts_json

            # Execute script
            # Create a namespace with context available
            namespace = {
                "context": self.context,
                "asyncio": asyncio,
                "__name__": "__main__",
            }

            # Execute the script code
            exec(self.script_code, namespace)

            # If script has a main function, run it
            if "main" in namespace and callable(namespace["main"]):
                await namespace["main"](self.context)

            script_logger.info("Script completed")
            self.status = ProfileStatus.IDLE

        except asyncio.CancelledError:
            script_logger.info("Script cancelled")
            raise
        except Exception as e:
            script_logger.error(f"Script error: {e}", exc_info=True)
            self.status = ProfileStatus.CRASHED
            raise
