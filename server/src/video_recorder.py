"""
FFmpeg-based video recorder for Xvfb displays.
Replaces Playwright's built-in recording with manual start/stop control.
"""

import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RecordingStatus:
    recording: bool
    duration_seconds: int = 0
    file_size_bytes: int = 0
    filename: Optional[str] = None


class VideoRecorder:
    """
    Manages an FFmpeg subprocess that captures an Xvfb display.

    Lifecycle:
        1. start() - Spawns ffmpeg, begins capturing
        2. get_status() - Returns live duration/size
        3. stop() - Sends SIGINT to finalize file, returns filename
    """

    def __init__(
        self,
        display: str,
        output_dir: Path,
        resolution: str = "1920x1080",
        framerate: int = 30
    ):
        """
        Args:
            display: Xvfb display string (e.g., ":100")
            output_dir: Directory to save video files
            resolution: Capture resolution
            framerate: Capture framerate
        """
        self.display = display
        self.output_dir = output_dir
        self.resolution = resolution
        self.framerate = framerate

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.process: Optional[asyncio.subprocess.Process] = None
        self.start_time: Optional[float] = None
        self.current_filename: Optional[str] = None
        self.current_filepath: Optional[Path] = None

        # Environment for subprocess (must include DISPLAY)
        self.env = {
            "DISPLAY": display,
            "PATH": "/usr/bin:/usr/local/bin:/bin",
            "HOME": str(Path.home())
        }

    async def start(self) -> str:
        """
        Start recording the Xvfb display.

        Returns:
            The filename of the recording (without path).

        Raises:
            RuntimeError: If already recording or ffmpeg fails to start.
        """
        if self.process and self.process.returncode is None:
            raise RuntimeError("Recording already in progress")

        # Generate filename
        timestamp = int(time.time())
        self.current_filename = f"rec_{timestamp}.mp4"
        self.current_filepath = self.output_dir / self.current_filename

        cmd = [
            "ffmpeg",
            "-y",                          # Overwrite output file
            "-f", "x11grab",               # Input format: X11 screen capture
            "-video_size", self.resolution,
            "-framerate", str(self.framerate),
            "-i", self.display,            # Input: Xvfb display
            "-c:v", "libx264",             # Video codec: H.264
            "-preset", "fast",             # Encoding preset (balance speed/quality)
            "-crf", "23",                  # Constant Rate Factor (18=high, 28=low)
            "-pix_fmt", "yuv420p",         # Pixel format (broad compatibility)
            "-movflags", "+faststart",     # Move MOOV atom to start for streaming
            "-loglevel", "error",          # Suppress verbose output
            str(self.current_filepath)
        ]

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                env=self.env
            )
            self.start_time = time.time()

            # Brief delay to ensure ffmpeg has started
            await asyncio.sleep(0.5)

            if self.process.returncode is not None:
                # Process already exited - read error
                stderr = b""
                if self.process.stderr:
                    stderr = await self.process.stderr.read()
                raise RuntimeError(
                    f"FFmpeg failed to start: {stderr.decode().strip()}"
                )

            logger.info(
                f"Recording started: {self.current_filename} "
                f"(display={self.display})"
            )
            return self.current_filename

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.process = None
            self.start_time = None
            self.current_filename = None
            self.current_filepath = None
            raise

    async def stop(self) -> Optional[str]:
        """
        Stop recording and finalize the video file.

        Sends SIGINT to FFmpeg to ensure proper file finalization
        (MOOV atom written, file header closed).

        Returns:
            The filename of the completed recording, or None if not recording.
        """
        if not self.process or self.process.returncode is not None:
            logger.warning("Stop called but no active recording")
            self.process = None
            self.start_time = None
            return None

        filename = self.current_filename
        filepath = self.current_filepath

        try:
            # Send SIGINT for graceful shutdown
            # This causes ffmpeg to write the file header and exit cleanly
            self.process.send_signal(signal.SIGINT)

            # Wait for process to finish (with timeout)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("FFmpeg didn't stop gracefully, killing")
                self.process.kill()
                await self.process.wait()

            logger.info(f"Recording stopped: {filename}")

        except ProcessLookupError:
            logger.warning("FFmpeg process already gone")
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
        finally:
            self.process = None
            self.start_time = None
            self.current_filename = None
            self.current_filepath = None

        return filename

    def get_status(self) -> RecordingStatus:
        """Get current recording status (non-blocking)."""
        if not self.process or self.process.returncode is not None:
            return RecordingStatus(recording=False)

        duration = int(time.time() - self.start_time) if self.start_time else 0
        file_size = 0
        if self.current_filepath and self.current_filepath.exists():
            file_size = self.current_filepath.stat().st_size

        return RecordingStatus(
            recording=True,
            duration_seconds=duration,
            file_size_bytes=file_size,
            filename=self.current_filename
        )

    async def cleanup(self):
        """Force stop any active recording (for shutdown)."""
        if self.process and self.process.returncode is None:
            try:
                self.process.send_signal(signal.SIGINT)
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None
        self.start_time = None
        self.current_filename = None
        self.current_filepath = None
