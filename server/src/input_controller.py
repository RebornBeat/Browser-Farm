"""
System-level input controller using xdotool.
Replaces Playwright's synthetic mouse/keyboard events with real X11 input.
The browser sees genuine OS-level input (isTrusted=true).
"""

import asyncio
import logging
import shutil
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class InputController:
    """
    Controls mouse and keyboard via xdotool on a specific Xvfb display.

    Each profile gets its own InputController instance bound to its display.
    All commands run as async subprocesses targeting $DISPLAY.
    """

    # Button mappings for xdotool
    BUTTON_MAP = {
        "left": 1,
        "middle": 2,
        "right": 3,
        "wheel_up": 4,
        "wheel_down": 5,
    }

    # Key mappings for modifiers
    MODIFIER_MAP = {
        "ctrl": "ctrl",
        "shift": "shift",
        "alt": "alt",
        "meta": "super",  # Windows/Super key
        "cmd": "super",
    }

    def __init__(self, display: str):
        """
        Args:
            display: Xvfb display string (e.g., ":100")
        """
        self.display = display
        self.env = {
            "DISPLAY": display,
            "PATH": "/usr/bin:/usr/local/bin:/bin",
            "HOME": str(__import__("pathlib").Path.home())
        }

        # Verify xdotool is available
        self._xdotool_available = shutil.which("xdotool") is not None
        if not self._xdotool_available:
            logger.error("xdotool not found! System input will not work.")
            logger.error("Install with: sudo apt install xdotool")

    async def _run_xdotool(self, args: List[str]) -> bool:
        """
        Execute an xdotool command asynchronously.

        Args:
            args: List of xdotool arguments (without 'xdotool' prefix)

        Returns:
            True if command succeeded, False otherwise.
        """
        if not self._xdotool_available:
            logger.error("xdotool not available")
            return False

        cmd = ["xdotool"] + args

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                env=self.env
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode().strip() if stderr else "Unknown error"
                logger.warning(f"xdotool command failed: {' '.join(args)} - {err}")
                return False

            return True

        except Exception as e:
            logger.error(f"xdotool execution error: {e}")
            return False

    # ==========================================
    # MOUSE
    # ==========================================

    async def mouse_move(self, x: int, y: int) -> bool:
        """Move mouse to absolute screen coordinates."""
        return await self._run_xdotool([
            "mousemove", "--sync", str(int(x)), str(int(y))
        ])

    async def mouse_move_relative(self, dx: int, dy: int) -> bool:
        """Move mouse by relative offset."""
        return await self._run_xdotool([
            "mousemove_relative", "--sync", str(int(dx)), str(int(dy))
        ])

    async def mouse_down(self, button: str = "left") -> bool:
        """Press and hold a mouse button."""
        btn = self.BUTTON_MAP.get(button, 1)
        return await self._run_xdotool(["mousedown", str(btn)])

    async def mouse_up(self, button: str = "left") -> bool:
        """Release a mouse button."""
        btn = self.BUTTON_MAP.get(button, 1)
        return await self._run_xdotool(["mouseup", str(btn)])

    async def mouse_click(
        self,
        button: str = "left",
        modifiers: Optional[List[str]] = None
    ) -> bool:
        """
        Click a mouse button (down + up).
        Optionally hold modifier keys during the click.
        """
        btn = self.BUTTON_MAP.get(button, 1)

        # Hold modifiers
        held_mods = []
        if modifiers:
            for mod in modifiers:
                mod_key = self.MODIFIER_MAP.get(mod.lower())
                if mod_key:
                    await self._run_xdotool(["keydown", mod_key])
                    held_mods.append(mod_key)

        # Click
        result = await self._run_xdotool(["click", str(btn)])

        # Release modifiers
        for mod_key in reversed(held_mods):
            await self._run_xdotool(["keyup", mod_key])

        return result

    async def mouse_double_click(self, button: str = "left") -> bool:
        """Double-click a mouse button."""
        btn = self.BUTTON_MAP.get(button, 1)
        return await self._run_xdotool(["click", "--repeat", "2", "--delay", "100", str(btn)])

    async def mouse_scroll(self, delta_y: int) -> bool:
        """
        Scroll the mouse wheel.
        Positive delta_y = scroll up, negative = scroll down.
        """
        clicks = abs(delta_y) // 100  # Adjust sensitivity
        if clicks == 0:
            clicks = 1

        button = "wheel_up" if delta_y > 0 else "wheel_down"
        btn = self.BUTTON_MAP[button]

        return await self._run_xdotool([
            "click", "--repeat", str(clicks), "--delay", "50", str(btn)
        ])

    async def batch_move(self, points: List[Dict]) -> bool:
        """
        Move mouse through a series of points in a SINGLE xdotool process.
        This prevents process-spawning latency that causes lag and missed clicks.

        Args:
            points: List of {"x": int, "y": int} dicts
        """
        if not points:
            return True

        # Build a single command string: "mousemove x1 y1 mousemove x2 y2 ..."
        args = []
        for point in points:
            x = int(point.get("x", 0))
            y = int(point.get("y", 0))
            args.extend(["mousemove", str(x), str(y)])

        return await self._run_xdotool(args)

    # ==========================================
    # KEYBOARD
    # ==========================================

    async def key_down(self, key: str) -> bool:
        """Press and hold a key."""
        return await self._run_xdotool(["keydown", key])

    async def key_up(self, key: str) -> bool:
        """Release a key."""
        return await self._run_xdotool(["keyup", key])

    async def key_press(self, key: str) -> bool:
        """Press and release a key."""
        return await self._run_xdotool(["key", key])

    async def type_text(self, text: str, delay_ms: int = 50) -> bool:
        """
        Type a string of text with delay between keystrokes.

        Args:
            text: The text to type
            delay_ms: Delay between keystrokes in milliseconds
        """
        if not text:
            return True

        return await self._run_xdotool([
            "type", "--delay", str(delay_ms), "--clearmodifiers", text
        ])

    async def type_key_combination(self, keys: List[str]) -> bool:
        """
        Type a key combination (e.g., ['ctrl', 'c']).
        """
        combo = "+".join(keys)
        return await self._run_xdotool(["key", combo])
