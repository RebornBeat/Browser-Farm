import asyncio
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Local Imports
from .models import (
    Profile, ProfileCreate, ProfileStatus, ProfileMetrics,
    ProxyConfig, Screenshot, Video, LogEntry, ServerHealth, ProfileMode
)
from .context_manager import ContextManager
from .xvfb_manager import XvfbManager
from .vnc_handler import VNCHandler
from .utils import generate_api_key, get_memory_usage, get_cached_cpu_usage

# Database Imports (To be created)
from .database import get_db, init_db, AsyncSessionLocal
from .models_db import DbProfile

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
# Runtime caches (Not persistent)
accounts_cache: Dict[str, Dict[str, dict]] = {}
shared_state_data: Dict[str, Any] = {}
command_center_id: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global context_manager, xvfb, command_center_id

    # Startup
    logger.info("Starting Browser Farm server...")

    # 1. Initialize Database
    await init_db()
    logger.info("✓ Database initialized")

    # 2. Initialize Xvfb Manager
    xvfb = XvfbManager()

    # 3. Start context manager
    data_dir = Path.home() / ".browser-farm" / "data"
    context_manager = ContextManager(data_dir)
    await context_manager.start()

    # 4. Crash Recovery Logic
    # If server restarted, any 'running' profiles in DB are actually dead.
    # We must mark them as STOPPED.
    async with AsyncSessionLocal() as session:
        stmt = select(DbProfile).where(DbProfile.status.in_([ProfileStatus.RUNNING, ProfileStatus.PAUSED]))
        result = await session.execute(stmt)
        active_profiles = result.scalars().all()

        if active_profiles:
            logger.warning(f"Found {len(active_profiles)} profiles in RUNNING/PAUSED state during startup. Marking as STOPPED.")
            for p in active_profiles:
                p.status = ProfileStatus.STOPPED
            await session.commit()

        # Check for existing Command Center
        cc_stmt = select(DbProfile).where(DbProfile.mode == ProfileMode.COMMAND_CENTER)
        cc_result = await session.execute(cc_stmt)
        cc_profile = cc_result.scalar_one_or_none()
        if cc_profile:
            command_center_id = cc_profile.id
            logger.info(f"Restored Command Center reference: {command_center_id}")

    logger.info(f"✓ Server running")
    logger.info(f"✓ API Key: {API_KEY}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if context_manager:
        await context_manager.stop()
    if xvfb:
        xvfb.stop_all()


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
    """Get server health and system metrics (Non-blocking)"""
    mem = get_memory_usage()
    uptime = int(time.time() - START_TIME)

    return ServerHealth(
        status="online",
        version="1.0.0",
        max_contexts=20,
        current_contexts=len(context_manager.contexts), # Live count from memory
        memory_total_mb=mem["total_mb"],
        memory_used_mb=mem["used_mb"],
        memory_available_mb=mem["available_mb"],
        cpu_usage=get_cached_cpu_usage(), # Non-blocking
        uptime_seconds=uptime
    )


@app.post("/proxies")
async def register_proxy(proxy: ProxyConfig, _=verify_api_key):
    """Register a proxy configuration"""
    context_manager.register_proxy(proxy)
    return {"status": "ok"}


@app.get("/profiles")
async def list_profiles(_=verify_api_key, db: AsyncSession = Depends(get_db)):
    """List all profiles with their status and metrics"""
    result = await db.execute(select(DbProfile))
    db_profiles = result.scalars().all()

    response_data = []
    for p in db_profiles:
        # Mix DB data with live runtime metrics if available
        metrics = context_manager.get_profile_metrics(p.id) if p.id in context_manager.contexts else {}

        response_data.append({
            "id": p.id,
            "name": p.name,
            "mode": p.mode.value,
            "status": p.status.value,
            "proxy_id": p.proxy_id,
            "memory_mb": metrics.get("memory_mb", 0),
            "cpu_percent": metrics.get("cpu_percent", 0),
            "uptime_seconds": 0,
            "last_screenshot": f"/screenshots/{p.id}_latest.png",
            "created_at": p.created_at.isoformat()
        })

    return {"profiles": response_data}


@app.post("/profiles")
async def create_profile(data: ProfileCreate, _=verify_api_key, db: AsyncSession = Depends(get_db)):
    """Create a new profile"""
    global command_center_id

    # Enforce Single Command Center Constraint
    if data.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id:
            raise HTTPException(
                status_code=400,
                detail=f"A Command Center profile already exists (ID: {command_center_id})"
            )
        command_center_id = "temp_placeholder" # Will be replaced by ID

    # Create DB Model
    profile_id = f"profile_{int(time.time() * 1000)}" # Unique ID based on timestamp

    db_profile = DbProfile(
        id=profile_id,
        name=data.name,
        mode=data.mode,
        proxy_id=data.proxy_id,
        user_agent=data.user_agent,
        timezone=data.timezone,
        locale=data.locale,
        geolocation=data.geolocation,
        scripts=data.scripts,
        requirements=data.requirements,
        memory_threshold_mb=data.memory_threshold_mb,
        status=ProfileStatus.IDLE
    )

    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)

    if data.mode == ProfileMode.COMMAND_CENTER:
        command_center_id = db_profile.id
        logger.info(f"Designated profile {profile_id} as Command Center.")

    logger.info(f"Created profile {profile_id} (Mode: {data.mode}, Proxy: {data.proxy_id or 'None'})")

    return {"id": profile_id, "status": "created"}


@app.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, _=verify_api_key, db: AsyncSession = Depends(get_db)):
    """Get detailed profile information"""
    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    metrics = context_manager.get_profile_metrics(profile_id) if profile_id in context_manager.contexts else {}

    return {
        "id": profile.id,
        "name": profile.name,
        "mode": profile.mode.value,
        "status": profile.status.value,
        "proxy_id": profile.proxy_id,
        "user_agent": profile.user_agent,
        "timezone": profile.timezone,
        "locale": profile.locale,
        "memory_mb": metrics.get("memory_mb", 0),
        "cpu_percent": metrics.get("cpu_percent", 0),
        "scripts": profile.scripts,
        "requirements": profile.requirements,
        "memory_threshold_mb": profile.memory_threshold_mb,
        "created_at": profile.created_at.isoformat()
    }


@app.post("/profiles/{profile_id}/start")
async def start_profile(
    profile_id: str,
    accounts: Dict[str, dict],
    _=verify_api_key,
    db: AsyncSession = Depends(get_db)
):
    """Start a profile (Launch browser and run scripts)"""
    global command_center_id

    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Double check Command Center constraint on start
    if profile.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id and command_center_id != profile_id:
             raise HTTPException(400, "A Command Center is already running.")

    # Update Status in DB
    profile.status = ProfileStatus.RUNNING
    await db.commit()

    accounts_cache[profile_id] = accounts
    display_str = "unknown"

    # Create context if not exists
    if profile_id not in context_manager.contexts:
        try:
            display_str = xvfb.start_display(profile_id)
            logger.info(f"Assigned display {display_str} to profile {profile_id}")
        except Exception as e:
            logger.error(f"Failed to start Xvfb for {profile_id}: {e}")
            profile.status = ProfileStatus.CRASHED
            await db.commit()
            raise HTTPException(500, "Failed to initialize virtual display")

        # Convert DB profile to Pydantic for context manager compatibility
        profile_pydantic = Profile.from_orm(profile) # Or construct manually if needed
        await context_manager.create_profile(profile_pydantic, accounts, display_str)
    else:
        info = xvfb.active_displays.get(profile_id)
        if info:
            display_str = f":{info[1]}"

    await context_manager.start_profile(profile_id)

    return {"status": "started", "display": display_str}


@app.post("/profiles/{profile_id}/pause")
async def pause_profile(profile_id: str, _=verify_api_key, db: AsyncSession = Depends(get_db)):
    """Pause a profile"""
    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    await context_manager.pause_profile(profile_id)

    profile.status = ProfileStatus.PAUSED
    await db.commit()

    return {"status": "paused"}


@app.post("/profiles/{profile_id}/stop")
async def stop_profile(profile_id: str, _=verify_api_key, db: AsyncSession = Depends(get_db)):
    """Stop a profile"""
    global command_center_id

    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    await context_manager.stop_profile(profile_id)
    xvfb.stop_display(profile_id)

    profile.status = ProfileStatus.STOPPED
    await db.commit()

    if command_center_id == profile_id:
        logger.info(f"Command Center {profile_id} stopped.")
        command_center_id = None

    return {"status": "stopped"}


@app.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, _=verify_api_key, db: AsyncSession = Depends(get_db)):
    """Delete a profile"""
    global command_center_id

    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile_id in context_manager.contexts:
        await context_manager.stop_profile(profile_id)

    if profile_id in xvfb.active_displays:
        xvfb.stop_display(profile_id)

    await db.delete(profile)
    await db.commit()

    if profile_id in accounts_cache:
        del accounts_cache[profile_id]

    if command_center_id == profile_id:
        command_center_id = None

    return {"status": "deleted"}


# ---------------------------------------------------------
# SCREENSHOTS & STREAMING
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------

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
