import subprocess
import os
import signal
import time
import logging

logger = logging.getLogger(__name__)


class XvfbManager:
    def __init__(self, display=":99", resolution="1920x1080x24"):
        self.display = display
        self.resolution = resolution
        self.process = None

    def start(self):
        """Start Xvfb virtual display"""
        try:
            # Check if Xvfb is already running
            if self._is_running():
                logger.info(f"Xvfb already running on {self.display}")
                os.environ["DISPLAY"] = self.display
                return

            # Start Xvfb
            cmd = [
                "Xvfb",
                self.display,
                "-screen", "0", self.resolution,
                "-ac",
                "+extension", "GLX",
                "+render",
                "-noreset"
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for Xvfb to be ready
            time.sleep(2)

            # Set DISPLAY environment variable
            os.environ["DISPLAY"] = self.display

            logger.info(f"✓ Xvfb started on {self.display}")

        except Exception as e:
            logger.error(f"Failed to start Xvfb: {e}")
            raise

    def _is_running(self):
        """Check if Xvfb is already running"""
        try:
            subprocess.run(
                ["xdpyinfo", "-display", self.display],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return True
        except:
            return False

    def stop(self):
        """Stop Xvfb"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            logger.info("Xvfb stopped")
