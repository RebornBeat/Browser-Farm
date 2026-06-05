import asyncio
import subprocess
import os
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
        self.process: Optional[asyncio.subprocess.Process] = None
        self.display: str = f":{base_display}"

        # Per-Profile Management
        # Structure: { profile_id: (process_handle, display_number) }
        self.active_displays: Dict[str, Tuple[asyncio.subprocess.Process, int]] = {}

        # Track used display numbers to find available slots quickly
        self._used_display_numbers: set = set()

    # ==========================================
    # Legacy Global Methods (Async Compatible)
    # ==========================================

    async def start(self):
        """Start the default global Xvfb virtual display (Legacy/Default)"""
        try:
            if await self._is_running(self.display):
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

            # Use asyncio subprocess
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            # Wait for Xvfb to be ready
            await asyncio.sleep(2)

            # Verify it started
            if not await self._is_running(self.display):
                 raise RuntimeError(f"Failed to start global Xvfb on {self.display}")

            os.environ["DISPLAY"] = self.display
            self._used_display_numbers.add(self.base_display)
            logger.info(f"✓ Xvfb started on {self.display}")

        except Exception as e:
            logger.error(f"Failed to start Xvfb: {e}")
            raise

    async def stop(self):
        """Stop the global Xvfb instance"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
            except ProcessLookupError:
                pass

            if self.base_display in self._used_display_numbers:
                self._used_display_numbers.remove(self.base_display)

            logger.info("Global Xvfb stopped")

    # ==========================================
    # Per-Profile Methods (Async Non-Blocking)
    # ==========================================

    async def start_display(self, profile_id: str) -> str:
        """
        Starts a dedicated Xvfb display for a specific profile ASYNCHRONOUSLY.
        This allows concurrent PyAutoGUI usage across multiple profiles.

        Args:
            profile_id: The unique ID of the profile.

        Returns:
            The display string (e.g., ":100") to be used for this profile.
        """
        # 1. Check if this profile already has a display
        if profile_id in self.active_displays:
            proc, display_num = self.active_displays[profile_id]
            display_str = f":{display_num}"
            logger.info(f"Reusing existing display {display_str} for profile {profile_id}")
            return display_str

        # 2. Find an available display number
        display_num = self._find_available_display()
        display_str = f":{display_num}"

        try:
            logger.info(f"Allocating display {display_str} for profile {profile_id}...")

            # --- CRITICAL FIX: Aggressive Cleanup ---
            # 1. Remove lock file
            lock_file = f"/tmp/.X{display_num}-lock"
            if os.path.exists(lock_file):
                logger.warning(f"Removing stale Xvfb lock file: {lock_file}")
                try:
                    # Run os.remove in executor to prevent blocking loop
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, os.remove, lock_file)
                except OSError as e:
                    logger.error(f"Failed to remove lock file: {e}")

            # 2. Kill any zombie process holding this display
            # We use pkill to ensure the port is free before we try to bind.
            try:
                # The '|| true' ensures the command doesn't throw error if no process found
                kill_cmd = f"pkill -f 'Xvfb {display_str}' || true"
                kill_proc = await asyncio.create_subprocess_shell(
                    kill_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await kill_proc.wait()
                logger.info(f"Killed any existing zombie processes for {display_str}")
            except Exception as e:
                logger.warning(f"Cleanup kill failed (safe to ignore): {e}")
            # -------------------------------------

            # 3. Launch Xvfb (Async)
            cmd = [
                "Xvfb",
                display_str,
                "-screen", "0", self.resolution,
                "-ac",
                "+extension", "GLX",
                "+render",
                "-noreset"
            ]

            # Redirect stderr to PIPE so we can capture WHY it fails if it crashes immediately
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )

            # 4. Wait and verify (Non-Blocking Poll)
            # Wait up to 5 seconds for display to be ready
            start_time = asyncio.get_event_loop().time()
            while True:
                if await self._is_running(display_str):
                    break

                if asyncio.get_event_loop().time() - start_time > 5:
                    # Timeout occurred
                    err_output = b""
                    # Try to read stderr to understand why it failed
                    if proc.stderr:
                        try:
                            # Read available error output
                            err_output = await asyncio.wait_for(proc.stderr.read(), timeout=0.5)
                        except: pass

                    # Kill the failed process
                    try:
                        proc.kill()
                        await proc.wait()
                    except: pass

                    err_msg = err_output.decode().strip() if err_output else "Unknown error (process exited or hung)"
                    raise RuntimeError(
                        f"Xvfb failed to start on {display_str} within 5s. "
                        f"Stderr: {err_msg}"
                    )

                await asyncio.sleep(0.2)

            # 5. Register
            self.active_displays[profile_id] = (proc, display_num)
            self._used_display_numbers.add(display_num)

            logger.info(f"✓ Xvfb started on {display_str} for profile {profile_id}")
            return display_str

        except Exception as e:
            logger.error(f"Failed to start display for {profile_id}: {e}")
            # Clean up if failed
            if display_num in self._used_display_numbers:
                self._used_display_numbers.remove(display_num)
            raise

    async def stop_display(self, profile_id: str):
        """
        Stops the Xvfb display associated with a specific profile.
        """
        if profile_id not in self.active_displays:
            logger.warning(f"No managed display found for profile {profile_id}")
            return

        proc, display_num = self.active_displays[profile_id]
        display_str = f":{display_num}"

        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"Error stopping display for {profile_id}: {e}")
        finally:
            # Cleanup references
            del self.active_displays[profile_id]
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
                # Note: We skip the _is_running check here to keep this sync/fast
                # The start_display will handle conflicts via lock file cleanup
                return candidate
            candidate += 1
            # Safety break to prevent infinite loops in extreme cases
            if candidate > self.base_display + 1000:
                raise RuntimeError("Could not find an available display number")

    async def _is_running(self, display: str) -> bool:
        """Check if Xvfb is running on a specific display ASYNCHRONOUSLY"""
        try:
            # xdpyinfo is used to verify the X server is accepting connections
            proc = await asyncio.create_subprocess_exec(
                "xdpyinfo", "-display", display,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def stop_all(self):
        """Stops all managed displays and the global instance."""
        # Stop all profile-specific displays
        # Convert to list to avoid modification during iteration
        for profile_id in list(self.active_displays.keys()):
            await self.stop_display(profile_id)

        # Stop global
        await self.stop()

        logger.info("All Xvfb instances stopped.")
