import asyncio
import logging
from typing import Dict
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class VNCHandler:
    def __init__(self, page: Page):
        self.page = page

    async def handle_mouse_move(self, x: int, y: int):
        """Handle mouse move event"""
        await self.page.mouse.move(x, y)

    async def handle_mouse_click(self, x: int, y: int, button: str = "left"):
        """Handle mouse click event"""
        await self.page.mouse.click(x, y, button=button)

    async def handle_keyboard(self, text: str):
        """Handle keyboard input"""
        await self.page.keyboard.type(text)

    async def handle_scroll(self, delta_y: int):
        """Handle scroll event"""
        await self.page.mouse.wheel(0, delta_y)

    async def process_action(self, action: Dict):
        """Process a control action"""
        action_type = action.get("type")

        if action_type == "mouse_move":
            await self.handle_mouse_move(action["x"], action["y"])

        elif action_type == "mouse_click":
            await self.handle_mouse_click(
                action["x"],
                action["y"],
                action.get("button", "left")
            )

        elif action_type == "keyboard":
            await self.handle_keyboard(action["text"])

        elif action_type == "scroll":
            await self.handle_scroll(action["delta_y"])
