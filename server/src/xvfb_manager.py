import subprocess
import os
import time
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class XvfbManager:
    def __init__(self, base_display: int = 99, resolution: str = "1920x1080x24"):
        """
        Initialize Xvfb Manager.

        Args:
            base_display: The starting display number (e.g., 99 means :99)
            resolution: Screen resolution and depth string.
        """
        self.base_display = base_display
        self.resolution = resolution

        # Global/Legacy process (kept for backwards compatibility or server-wide needs)
        self.process: Optional[subprocess.Popen] = None
        self.display: str = f":{base_display}"

        # Per-Profile Management
        # Structure: { profile_id: (process_handle, display_number) }
        self.managed_displays: Dict[str, Tuple[subprocess.Popen, int]] = {}

        # Track used display numbers to find available slots quickly
        self._used_display_numbers: set = set()

    # ==========================================
    # Legacy Global Methods (Preserved)
    # ==========================================

    def start(self):
        """Start the default global Xvfb virtual display (Legacy/Default)"""
        try:
            if self._is_running(self.display):
                logger.info(f"Xvfb already running on {self.display}")
                os.environ["DISPLAY"] = self.display
                return

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

            time.sleep(2)  # Wait for Xvfb to be ready

            # Verify it started
            if not self._is_running(self.display):
                 raise RuntimeError(f"Failed to start global Xvfb on {self.display}")

            os.environ["DISPLAY"] = self.display
            self._used_display_numbers.add(self.base_display)
            logger.info(f"✓ Xvfb started on {self.display}")

        except Exception as e:
            logger.error(f"Failed to start Xvfb: {e}")
            raise

    def stop(self):
        """Stop the global Xvfb instance"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

            if self.base_display in self._used_display_numbers:
                self._used_display_numbers.remove(self.base_display)

            logger.info("Global Xvfb stopped")

    # ==========================================
    # Per-Profile Methods (New)
    # ==========================================

    def start_display(self, profile_id: str) -> str:
        """
        Starts a dedicated Xvfb display for a specific profile.
        This allows concurrent PyAutoGUI usage across multiple profiles.

        Args:
            profile_id: The unique ID of the profile.

        Returns:
            The display string (e.g., ":100") to be used for this profile.
        """
        # 1. Check if this profile already has a display
        if profile_id in self.managed_displays:
            proc, display_num = self.managed_displays[profile_id]
            display_str = f":{display_num}"
            logger.info(f"Reusing existing display {display_str} for profile {profile_id}")
            return display_str

        # 2. Find an available display number
        display_num = self._find_available_display()
        display_str = f":{display_num}"

        try:
            logger.info(f"Allocating display {display_str} for profile {profile_id}...")

            # 3. Launch Xvfb
            cmd = [
                "Xvfb",
                display_str,
                "-screen", "0", self.resolution,
                "-ac",
                "+extension", "GLX",
                "+render",
                "-noreset"
            ]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # 4. Wait and verify
            time.sleep(1)
            if not self._is_running(display_str):
                raise RuntimeError(f"Xvfb failed to start on {display_str}")

            # 5. Register
            self.managed_displays[profile_id] = (proc, display_num)
            self._used_display_numbers.add(display_num)

            logger.info(f"✓ Xvfb started on {display_str} for profile {profile_id}")
            return display_str

        except Exception as e:
            logger.error(f"Failed to start display for {profile_id}: {e}")
            # Clean up if failed
            if display_num in self._used_display_numbers:
                self._used_display_numbers.remove(display_num)
            raise

    def stop_display(self, profile_id: str):
        """
        Stops the Xvfb display associated with a specific profile.
        """
        if profile_id not in self.managed_displays:
            logger.warning(f"No managed display found for profile {profile_id}")
            return

        proc, display_num = self.managed_displays[profile_id]
        display_str = f":{display_num}"

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            logger.error(f"Error stopping display for {profile_id}: {e}")
        finally:
            # Cleanup references
            del self.managed_displays[profile_id]
            if display_num in self._used_display_numbers:
                self._used_display_numbers.remove(display_num)
            logger.info(f"✓ Xvfb stopped on {display_str} for profile {profile_id}")

    # ==========================================
    # Helpers
    # ==========================================

    def _find_available_display(self) -> int:
        """Finds the next available display number."""
        # Start searching from base_display + 1 (assuming base is reserved for global)
        candidate = self.base_display + 1
        while True:
            if candidate not in self._used_display_numbers:
                # Double check it's not used by an external process
                if not self._is_running(f":{candidate}"):
                    return candidate
            candidate += 1
            # Safety break to prevent infinite loops in extreme cases
            if candidate > self.base_display + 1000:
                raise RuntimeError("Could not find an available display number")

    def _is_running(self, display: str) -> bool:
        """Check if Xvfb is running on a specific display"""
        try:
            subprocess.run(
                ["xdpyinfo", "-display", display],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=2
            )
            return True
        except:
            return False

    def stop_all(self):
        """Stops all managed displays and the global instance."""
        # Stop all profile-specific displays
        # Convert to list to avoid modification during iteration
        for profile_id in list(self.managed_displays.keys()):
            self.stop_display(profile_id)

        # Stop global
        self.stop()

        logger.info("All Xvfb instances stopped.")
