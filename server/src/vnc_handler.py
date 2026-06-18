"""
Enhanced VNC Handler with system-level input support.
Uses InputController (xdotool) for genuine OS-level mouse/keyboard events.
Supports: drag, right-click, middle-click, modifiers, batch movements.
"""

import logging
from typing import Dict, Optional
from playwright.async_api import Page
from .input_controller import InputController

logger = logging.getLogger(__name__)


class VNCHandler:
    """
    Processes WebSocket control messages and translates them to
    system-level input via InputController (xdotool).

    This replaces Playwright's synthetic mouse/keyboard with
    genuine X11 input that the browser trusts (isTrusted=true).
    """

    def __init__(self, input_controller: InputController, page: Page):
        """
        Args:
            input_controller: System-level input controller for the profile's display
            page: Playwright page (used for fallback scroll only)
        """
        self.input = input_controller
        self.page = page
        # Track mouse button state for drag operations
        self._mouse_down = False
        self._drag_button = None

    async def process_action(self, action: Dict):
        """Process a control action from the WebSocket."""
        action_type = action.get("type")

        try:
            if action_type == "batch_move":
                await self._handle_batch_move(action.get("points", []))

            elif action_type == "mouse_move":
                await self._handle_mouse_move(action["x"], action["y"])

            elif action_type == "mouse_down":
                await self._handle_mouse_down(
                    action.get("x"),
                    action.get("y"),
                    action.get("button", "left")
                )

            elif action_type == "mouse_up":
                await self._handle_mouse_up(
                    action.get("x"),
                    action.get("y"),
                    action.get("button", "left")
                )

            elif action_type == "mouse_click":
                await self._handle_mouse_click(
                    action["x"],
                    action["y"],
                    action.get("button", "left"),
                    action.get("modifiers", [])
                )

            elif action_type == "mouse_double_click":
                await self._handle_mouse_double_click(
                    action["x"],
                    action["y"],
                    action.get("button", "left")
                )

            elif action_type == "scroll":
                await self._handle_scroll(action.get("delta_y", 0))

            elif action_type == "key_down":
                await self._handle_key_down(action.get("key", ""))

            elif action_type == "key_up":
                await self._handle_key_up(action.get("key", ""))

            elif action_type == "key_press":
                await self._handle_key_press(action.get("key", ""))

            elif action_type == "type":
                await self._handle_type(action.get("text", ""), action.get("delay_ms", 50))

            else:
                logger.warning(f"Unknown action type: {action_type}")

        except Exception as e:
            logger.error(f"Error processing action {action_type}: {e}")

    # ==========================================
    # MOUSE HANDLERS
    # ==========================================

    async def _handle_mouse_move(self, x: int, y: int):
        """Single mouse move (legacy support)."""
        await self.input.mouse_move(x, y)

    async def _handle_batch_move(self, points: list):
        """
        Process a batch of mouse movement points.
        Each point is {"x": int, "y": int, "t": int}.
        This preserves the movement curve for anti-detection.
        """
        if not points:
            return
        await self.input.batch_move(points)

    async def _handle_mouse_down(self, x: Optional[int], y: Optional[int], button: str = "left"):
        """Press mouse button down (start of drag or click)."""
        if x is not None and y is not None:
            await self.input.mouse_move(x, y)
        await self.input.mouse_down(button)
        self._mouse_down = True
        self._drag_button = button

    async def _handle_mouse_up(self, x: Optional[int], y: Optional[int], button: str = "left"):
        """Release mouse button (end of drag or click)."""
        if x is not None and y is not None:
            await self.input.mouse_move(x, y)
        await self.input.mouse_up(button)
        self._mouse_down = False
        self._drag_button = None

    async def _handle_mouse_click(
        self,
        x: int,
        y: int,
        button: str = "left",
        modifiers: list = None
    ):
        """Click (down + up) with optional modifier keys."""
        await self.input.mouse_move(x, y)
        await self.input.mouse_click(button=button, modifiers=modifiers)

    async def _handle_mouse_double_click(self, x: int, y: int, button: str = "left"):
        """Double-click."""
        await self.input.mouse_move(x, y)
        await self.input.mouse_double_click(button)

    # ==========================================
    # SCROLL HANDLER
    # ==========================================

    async def _handle_scroll(self, delta_y: int):
        """Scroll the mouse wheel."""
        await self.input.mouse_scroll(delta_y)

    # ==========================================
    # KEYBOARD HANDLERS
    # ==========================================

    async def _handle_key_down(self, key: str):
        """Press and hold a key."""
        if key:
            await self.input.key_down(key)

    async def _handle_key_up(self, key: str):
        """Release a key."""
        if key:
            await self.input.key_up(key)

    async def _handle_key_press(self, key: str):
        """Press and release a key."""
        if key:
            await self.input.key_press(key)

    async def _handle_type(self, text: str, delay_ms: int = 50):
        """Type a string of text."""
        if text:
            await self.input.type_text(text, delay_ms)
