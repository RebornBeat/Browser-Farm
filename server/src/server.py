import asyncio
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .models import (
    Profile, ProfileCreate, ProfileStatus, ProfileMetrics,
    ProxyConfig, Screenshot, Video, LogEntry, ServerHealth, ProfileMode
)
from .context_manager import ContextManager
from .xvfb_manager import XvfbManager
from .vnc_handler import VNCHandler
from .utils import generate_api_key, get_memory_usage, get_cpu_usage

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
API_KEY = generate_api_key()
START_TIME = time.time()
context_manager: Optional[ContextManager] = None
xvfb: Optional[XvfbManager] = None
profiles: Dict[str, Profile] = {}
accounts_cache: Dict[str, Dict[str, dict]] = {}  # profile_id -> accounts

# --- NEW GLOBAL STATE ---
shared_state_data: Dict[str, Any] = {}  # Shared State for Inter-Profile Communication
command_center_id: Optional[str] = None # Enforce Single Command Center


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global context_manager, xvfb

    # Startup
    logger.info("Starting Browser Farm server...")

    # Initialize Xvfb Manager (Per-Profile Display Support)
    xvfb = XvfbManager()
    # We don't start a global display anymore; we start them per profile.
    # But we keep the manager instance.

    # Start context manager
    data_dir = Path.home() / ".browser-farm" / "data"
    context_manager = ContextManager(data_dir)
    await context_manager.start()

    logger.info(f"✓ Server running")
    logger.info(f"✓ API Key: {API_KEY}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if context_manager:
        await context_manager.stop()
    if xvfb:
        xvfb.stop() # Cleanup any remaining displays


app = FastAPI(
    title="Browser Farm",
    description="Distributed browser automation platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------
# SHARED STATE ENDPOINTS (Inter-Profile Communication)
# ---------------------------------------------------------

@app.post("/state/{key}")
async def set_shared_state(key: str, value: Dict[Any, Any], _=verify_api_key):
    """Set a value in the shared state"""
    shared_state_data[key] = value
    return {"status": "ok"}

@app.get("/state/{key}")
async def get_shared_state(key: str, _=verify_api_key):
    """Get a value from the shared state"""
    return shared_state_data.get(key, {})

@app.delete("/state/{key}")
async def delete_shared_state(key: str, _=verify_api_key):
    """Delete a value from the shared state"""
    if key in shared_state_data:
        del shared_state_data[key]
    return {"status": "ok"}

# ---------------------------------------------------------
# CORE ENDPOINTS
# ---------------------------------------------------------

@app.get("/health", response_model=ServerHealth)
async def health():
    """Get server health"""
    mem = get_memory_usage()
    uptime = int(time.time() - START_TIME)

    return ServerHealth(
        status="online",
        version="1.0.0",
        max_contexts=20,
        current_contexts=len(profiles),
        memory_total_mb=mem["total_mb"],
        memory_used_mb=mem["used_mb"],
        memory_available_mb=mem["available_mb"],
        cpu_usage=get_cpu_usage(),
        uptime_seconds=uptime
    )


@app.post("/proxies")
async def register_proxy(proxy: ProxyConfig, _=verify_api_key):
    """Register a proxy"""
    context_manager.register_proxy(proxy)
    return {"status": "ok"}


@app.get("/profiles")
async def list_profiles(_=verify_api_key):
    """List all profiles"""
    result = []
    for profile_id, profile in profiles.items():
        metrics = context_manager.get_profile_metrics(profile_id) if profile_id in context_manager.contexts else {}

        result.append({
            "id": profile.id,
            "name": profile.name,
            "mode": profile.mode.value, # Include mode
            "status": context_manager.get_profile_status(profile_id).value,
            "proxy_id": profile.proxy_id,
            "memory_mb": metrics.get("memory_mb", 0),
            "cpu_percent": metrics.get("cpu_percent", 0),
            "uptime_seconds": 0,  # TODO: track uptime
            "last_screenshot": f"/screenshots/{profile_id}_latest.png",
            "created_at": profile.created_at.isoformat()
        })

    return {"profiles": result}


@app.post("/profiles")
async def create_profile(data: ProfileCreate, _=verify_api_key):
    """Create a new profile"""
    global command_center_id

    profile_id = f"profile_{len(profiles) + 1:03d}"

    # Enforce Single Command Center Constraint
    if data.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id:
            raise HTTPException(
                status_code=400,
                detail=f"A Command Center profile already exists (ID: {command_center_id})"
            )
        command_center_id = profile_id
        logger.info(f"Designated profile {profile_id} as Command Center.")

    profile = Profile(
        id=profile_id,
        name=data.name,
        mode=data.mode,
        proxy_id=data.proxy_id,
        user_agent=data.user_agent,
        timezone=data.timezone,
        locale=data.locale,
        geolocation=data.geolocation,
        scripts=data.scripts,          # Updated to list
        requirements=data.requirements, # New field
        memory_threshold_mb=data.memory_threshold_mb,
        status=ProfileStatus.IDLE
    )

    profiles[profile_id] = profile
    accounts_cache[profile_id] = {}

    logger.info(f"Created profile {profile_id} (Mode: {data.mode})")

    return {"id": profile_id, "status": "created"}


@app.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, _=verify_api_key):
    """Get profile details"""
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profiles[profile_id]
    metrics = context_manager.get_profile_metrics(profile_id) if profile_id in context_manager.contexts else {}

    return {
        "id": profile.id,
        "name": profile.name,
        "mode": profile.mode.value,
        "status": context_manager.get_profile_status(profile_id).value,
        "proxy_id": profile.proxy_id,
        "user_agent": profile.user_agent,
        "timezone": profile.timezone,
        "locale": profile.locale,
        "memory_mb": metrics.get("memory_mb", 0),
        "cpu_percent": metrics.get("cpu_percent", 0),
        "scripts": profile.scripts, # Return scripts list
        "requirements": profile.requirements,
        "memory_threshold_mb": profile.memory_threshold_mb,
        "created_at": profile.created_at.isoformat()
    }


@app.post("/profiles/{profile_id}/start")
async def start_profile(
    profile_id: str,
    accounts: Dict[str, dict],
    _=verify_api_key
):
    """Start a profile"""
    global command_center_id

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profiles[profile_id]
    accounts_cache[profile_id] = accounts

    # Double check Command Center constraint on start
    if profile.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id and command_center_id != profile_id:
             raise HTTPException(400, "A Command Center is already running.")

    # Create context if not exists
    if profile_id not in context_manager.contexts:
        # --- NEW: Start Dedicated Xvfb Display ---
        try:
            display_str = xvfb.start_display(profile_id)
            logger.info(f"Assigned display {display_str} to profile {profile_id}")
        except Exception as e:
            logger.error(f"Failed to start Xvfb for {profile_id}: {e}")
            raise HTTPException(500, "Failed to initialize virtual display")

        # Pass display_str to context manager
        await context_manager.create_profile(profile, accounts, display_str)

    await context_manager.start_profile(profile_id)

    return {"status": "started", "display": xvfb.active_displays.get(profile_id, "unknown")}


@app.post("/profiles/{profile_id}/pause")
async def pause_profile(profile_id: str, _=verify_api_key):
    """Pause a profile"""
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    await context_manager.pause_profile(profile_id)
    return {"status": "paused"}


@app.post("/profiles/{profile_id}/stop")
async def stop_profile(profile_id: str, _=verify_api_key):
    """Stop a profile"""
    global command_center_id

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Stop context
    await context_manager.stop_profile(profile_id)

    # --- NEW: Stop Xvfb Display ---
    xvfb.stop_display(profile_id)

    # Clear Command Center tracking if this was it
    if command_center_id == profile_id:
        logger.info(f"Command Center {profile_id} stopped.")
        command_center_id = None

    return {"status": "stopped"}


@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, _=verify_api_key):
    """Delete a profile"""
    global command_center_id

    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Stop if running
    if profile_id in context_manager.contexts:
        await context_manager.stop_profile(profile_id)

    # Cleanup Xvfb if somehow still running
    if profile_id in xvfb.active_displays:
        xvfb.stop_display(profile_id)

    # Cleanup state
    del profiles[profile_id]
    if profile_id in accounts_cache:
        del accounts_cache[profile_id]

    if command_center_id == profile_id:
        command_center_id = None

    return {"status": "deleted"}


@app.get("/profiles/{profile_id}/screen")
async def get_screen(profile_id: str, _=verify_api_key):
    """Get live screenshot"""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    screenshot = await context_manager.get_screenshot(profile_id)

    return StreamingResponse(
        iter([screenshot]),
        media_type="image/png"
    )


@app.websocket("/profiles/{profile_id}/stream")
async def stream_screen(websocket: WebSocket, profile_id: str):
    """Stream live screenshots via WebSocket"""
    await websocket.accept()

    try:
        while True:
            if profile_id not in context_manager.contexts:
                await websocket.close()
                break

            screenshot = await context_manager.get_screenshot(profile_id)
            await websocket.send_bytes(screenshot)

            await asyncio.sleep(0.1)  # 10 FPS

    except WebSocketDisconnect:
        pass


@app.websocket("/profiles/{profile_id}/control")
async def control_screen(websocket: WebSocket, profile_id: str):
    """Control browser via WebSocket"""
    await websocket.accept()

    if profile_id not in context_manager.contexts:
        await websocket.close()
        return

    context = context_manager.contexts[profile_id]
    pages = context.pages

    if not pages:
        await websocket.close()
        return

    page = pages[0]
    handler = VNCHandler(page)

    try:
        while True:
            message = await websocket.receive_json()
            await handler.process_action(message)

    except WebSocketDisconnect:
        pass


@app.post("/profiles/{profile_id}/screenshot")
async def take_screenshot(profile_id: str, _=verify_api_key):
    """Take and save screenshot"""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    filename = await context_manager.save_screenshot(profile_id)

    return {
        "id": filename.replace(".png", ""),
        "url": f"/screenshots/{filename}"
    }


@app.get("/profiles/{profile_id}/screenshots")
async def list_screenshots(profile_id: str, _=verify_api_key):
    """List all screenshots for profile"""
    screenshot_dir = context_manager.data_dir / "screenshots"
    files = sorted(screenshot_dir.glob(f"{profile_id}_*.png"), reverse=True)

    screenshots = []
    for file in files:
        screenshots.append({
            "id": file.stem,
            "timestamp": file.stat().st_mtime,
            "url": f"/screenshots/{file.name}",
            "size_bytes": file.stat().st_size
        })

    return {"screenshots": screenshots}


@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str, _=verify_api_key):
    """Get screenshot file"""
    filepath = context_manager.data_dir / "screenshots" / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(filepath)


@app.get("/profiles/{profile_id}/metrics")
async def get_metrics(profile_id: str, _=verify_api_key):
    """Get profile metrics"""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    metrics = context_manager.get_profile_metrics(profile_id)

    return metrics


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Browser Farm Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", default=8080, type=int, help="Port to bind to")
    parser.add_argument("--dev", action="store_true", help="Development mode")

    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "browser_farm.server:app",
        host=args.host,
        port=args.port,
        reload=args.dev
    )


if __name__ == "__main__":
    main()
