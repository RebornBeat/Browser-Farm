import asyncio
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header, Depends, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func

# Local Imports
from .models import (
    Profile, ProfileCreate, ProfileStatus, ProfileMetrics,
    ProxyConfig, Screenshot, Video, LogEntry, ServerHealth, ProfileMode
)
from .context_manager import ContextManager
from .xvfb_manager import XvfbManager
from .vnc_handler import VNCHandler
from .utils import generate_api_key, get_memory_usage, get_cached_cpu_usage

# Database Imports
from .database import get_db, init_db, AsyncSessionLocal
from .models_db import DbProfile, DbProxyHistory

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


# ---------------------------------------------------------
# BACKGROUND TASKS
# ---------------------------------------------------------

async def initialize_profile_task(profile_id: str, profile_pydantic: Profile, accounts: Dict[str, dict]):
    """
    Heavy initialization logic that runs in the background.
    This prevents the HTTP request from timing out.
    """
    try:
        # 1. Create the browser context (Heavy operation)
        await context_manager.create_profile(profile_pydantic, accounts)

        # 2. Start execution
        await context_manager.start_profile(profile_id)

        # 3. Update Database to RUNNING
        async with AsyncSessionLocal() as db:
            stmt = select(DbProfile).where(DbProfile.id == profile_id)
            result = await db.execute(stmt)
            p = result.scalar_one()
            p.status = ProfileStatus.RUNNING
            await db.commit()
            logger.info(f"Profile {profile_id} background initialization successful.")

    except Exception as e:
        logger.error(f"Background initialization failed for {profile_id}: {e}")

        # Update Database to CRASHED
        async with AsyncSessionLocal() as db:
            stmt = select(DbProfile).where(DbProfile.id == profile_id)
            result = await db.execute(stmt)
            p = result.scalar_one_or_none()
            if p:
                p.status = ProfileStatus.CRASHED
                await db.commit()

        # Cleanup resources if partially created
        if profile_id in context_manager.browsers or profile_id in context_manager.xvfb_manager.active_displays:
             await context_manager.stop_profile(profile_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global context_manager, xvfb, command_center_id

    # Startup
    logger.info("Starting Browser Farm server...")

    # 1. Initialize Database
    await init_db()
    logger.info("✓ Database initialized")

    # 2. Initialize Xvfb Manager (Global/Legacy)
    xvfb = XvfbManager()

    # 3. Start context manager
    data_dir = Path.home() / ".browser-farm" / "data"
    context_manager = ContextManager(data_dir)
    await context_manager.start()

    # 4. Crash Recovery Logic
    # If server restarted, any 'running' profiles in DB are actually dead.
    # We must mark them as STOPPED.
    async with AsyncSessionLocal() as session:
        stmt = select(DbProfile).where(DbProfile.status.in_([ProfileStatus.RUNNING, ProfileStatus.PAUSED, ProfileStatus.INITIALIZING]))
        result = await session.execute(stmt)
        active_profiles = result.scalars().all()

        if active_profiles:
            logger.warning(f"Found {len(active_profiles)} profiles in ACTIVE state during startup. Marking as STOPPED.")
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
        # Stop all managed displays on shutdown
        await xvfb.stop_all()


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
        current_contexts=len(context_manager.contexts),
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

    if data.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id:
            raise HTTPException(
                status_code=400,
                detail=f"A Command Center profile already exists (ID: {command_center_id})"
            )
        command_center_id = "temp_placeholder"

    profile_id = f"profile_{int(time.time() * 1000)}"

    db_profile = DbProfile(
        id=profile_id,
        name=data.name,
        mode=data.mode,
        proxy_id=data.proxy_id,
        user_agent=data.user_agent,
        timezone=data.timezone,
        locale=data.locale,
        geolocation=data.geolocation,
        # NEW: Browser engine and fingerprint fields
        browser_engine=data.browser_engine,
        os_fingerprint=data.os_fingerprint,
        gpu_vendor=data.gpu_vendor,
        gpu_renderer=data.gpu_renderer,
        hardware_concurrency=data.hardware_concurrency,
        device_memory=data.device_memory,
        # Existing fields
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

    logger.info(
        f"Created profile {profile_id} "
        f"(Engine: {data.browser_engine}, OS: {data.os_fingerprint}, "
        f"Mode: {data.mode}, Proxy: {data.proxy_id or 'None'})"
    )

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
        # NEW fields
        "browser_engine": profile.browser_engine,
        "browser_version": profile.browser_version,
        "os_fingerprint": profile.os_fingerprint,
        "gpu_vendor": profile.gpu_vendor,
        "gpu_renderer": profile.gpu_renderer,
        "hardware_concurrency": profile.hardware_concurrency,
        "device_memory": profile.device_memory,
        "last_warmed": profile.last_warmed.isoformat() if profile.last_warmed else None,
        # Existing fields
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
    background_tasks: BackgroundTasks,
    _=verify_api_key,
    db: AsyncSession = Depends(get_db)
):
    """
    Start a profile.
    Returns immediately with status 'initializing'.
    Actual startup happens in background to prevent timeouts.
    """
    global command_center_id

    result = await db.execute(select(DbProfile).where(DbProfile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Double check Command Center constraint on start
    if profile.mode == ProfileMode.COMMAND_CENTER:
        if command_center_id and command_center_id != profile_id:
             raise HTTPException(400, "A Command Center is already running.")

    # Update Status in DB immediately
    profile.status = ProfileStatus.INITIALIZING
    await db.commit()

    accounts_cache[profile_id] = accounts

    # Convert DB profile to Pydantic for context manager
    profile_data = {
        "id": profile.id,
        "name": profile.name,
        "mode": profile.mode,
        "proxy_id": profile.proxy_id,
        "user_agent": profile.user_agent,
        "timezone": profile.timezone,
        "locale": profile.locale,
        "geolocation": profile.geolocation,
        # NEW fields
        "browser_engine": profile.browser_engine,
        "browser_version": profile.browser_version,
        "os_fingerprint": profile.os_fingerprint,
        "gpu_vendor": profile.gpu_vendor,
        "gpu_renderer": profile.gpu_renderer,
        "hardware_concurrency": profile.hardware_concurrency,
        "device_memory": profile.device_memory,
        "last_warmed": profile.last_warmed,
        # Existing fields
        "scripts": profile.scripts,
        "requirements": profile.requirements,
        "memory_threshold_mb": profile.memory_threshold_mb,
        "status": profile.status,
        "created_at": profile.created_at
    }
    profile_pydantic = Profile(**profile_data)

    # Schedule the heavy startup logic in the background
    background_tasks.add_task(initialize_profile_task, profile_id, profile_pydantic, accounts)

    return {"status": "initializing"}


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

    # ContextManager handles Xvfb cleanup internally
    await context_manager.stop_profile(profile_id)

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
        # ContextManager handles Xvfb cleanup internally
        await context_manager.stop_profile(profile_id)

    await db.delete(profile)
    await db.commit()

    if profile_id in accounts_cache:
        del accounts_cache[profile_id]

    if command_center_id == profile_id:
        command_center_id = None

    return {"status": "deleted"}


# ---------------------------------------------------------
# NAVIGATION ENDPOINTS (NEW)
# ---------------------------------------------------------

@app.post("/profiles/{profile_id}/navigate")
async def navigate_profile(profile_id: str, url: str, _=verify_api_key):
    """
    Navigate the active page to a specific URL.
    Used for Manual mode control.
    """
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    context = context_manager.contexts[profile_id]
    pages = context.pages

    # If no page exists, create one
    if not pages:
        page = await context.new_page()
    else:
        page = pages[-1]

    try:
        # Navigate and wait for DOM content
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return {"status": "ok", "url": page.url}
    except Exception as e:
        logger.error(f"Navigation failed for {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")


@app.post("/profiles/{profile_id}/refresh")
async def refresh_profile(profile_id: str, _=verify_api_key):
    """Refresh the current page."""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    pages = context_manager.contexts[profile_id].pages
    if not pages:
        raise HTTPException(status_code=400, detail="No active page to refresh")

    try:
        await pages[-1].reload()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/{profile_id}/go_back")
async def go_back_profile(profile_id: str, _=verify_api_key):
    """Go back in browser history."""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    pages = context_manager.contexts[profile_id].pages
    if not pages:
        raise HTTPException(status_code=400, detail="No active page")

    try:
        await pages[-1].go_back()
        return {"status": "ok"}
    except Exception as e:
        # Playwright throws if no history
        logger.warning(f"Go back failed for {profile_id}: {e}")
        return {"status": "ok"}


# ---------------------------------------------------------
# HISTORY & COMPLIANCE
# ---------------------------------------------------------

@app.post("/history/record")
async def record_proxy_history(
    account_id: str,
    proxy_id: str,
    website: str,
    _=verify_api_key,
    db: AsyncSession = Depends(get_db)
):
    """
    Record that an account used a specific proxy for a specific website.
    Enforces '1 Account per Website per Proxy' logic.
    """
    # Check for conflicts
    stmt = select(DbProxyHistory).where(
        DbProxyHistory.account_id == account_id,
        DbProxyHistory.website == website
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        if existing.proxy_id != proxy_id:
            # Conflict: Account used this website with a DIFFERENT proxy
            raise HTTPException(
                status_code=400,
                detail=f"Conflict: Account {account_id} already used {website} with proxy {existing.proxy_id}"
            )
        # Update timestamp
        existing.last_used = func.now()
    else:
        # Create new record
        new_entry = DbProxyHistory(
            account_id=account_id,
            proxy_id=proxy_id,
            website=website
        )
        db.add(new_entry)

    await db.commit()
    return {"status": "recorded"}


# ---------------------------------------------------------
# SCREENSHOTS, VIDEOS & STREAMING
# ---------------------------------------------------------

@app.get("/profiles/{profile_id}/screen")
async def get_screen(profile_id: str, _=verify_api_key):
    """Get live screenshot (with crash protection)"""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")

    try:
        screenshot = await context_manager.get_screenshot(profile_id)
        return StreamingResponse(iter([screenshot]), media_type="image/png")
    except Exception as e:
        # If Playwright fails to capture (e.g., page transitioning, X busy),
        # return a placeholder instead of a 500 error to keep the client stable.
        logger.warning(f"Screenshot capture failed for {profile_id}: {e}. Returning placeholder.")
        placeholder = context_manager._generate_placeholder_image("Stream Paused...")
        return StreamingResponse(iter([placeholder]), media_type="image/png")


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
    """Control browser via WebSocket with system-level input."""
    await websocket.accept()

    if profile_id not in context_manager.contexts:
        await websocket.close()
        return

    # Get InputController for this profile's display
    input_controller = context_manager.get_input_controller(profile_id)
    if not input_controller:
        logger.error(f"No InputController for profile {profile_id}")
        await websocket.close()
        return

    context = context_manager.contexts[profile_id]
    pages = context.pages

    if not pages:
        await websocket.close()
        return

    page = pages[0]
    handler = VNCHandler(input_controller, page)

    try:
        while True:
            message = await websocket.receive_json()
            await handler.process_action(message)

    except WebSocketDisconnect:
        # Ensure mouse button is released on disconnect (prevent stuck drag)
        try:
            await input_controller.mouse_up("left")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Control WebSocket error: {e}")
        try:
            await input_controller.mouse_up("left")
        except Exception:
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


@app.post("/profiles/{profile_id}/recording/start")
async def start_recording(profile_id: str, _=verify_api_key):
    """Start video recording for a profile."""
    if profile_id not in context_manager.contexts:
        raise HTTPException(status_code=404, detail="Profile not running")
    try:
        filename = await context_manager.start_recording(profile_id)
        return {"status": "recording", "filename": filename}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/profiles/{profile_id}/recording/stop")
async def stop_recording(profile_id: str, _=verify_api_key):
    """Stop video recording for a profile."""
    if profile_id not in context_manager.recorders:
        raise HTTPException(status_code=404, detail="Profile not found")
    filename = await context_manager.stop_recording(profile_id)
    return {"status": "stopped", "filename": filename}


@app.get("/profiles/{profile_id}/recording/status")
async def get_recording_status(profile_id: str, _=verify_api_key):
    """Get recording status for a profile."""
    if profile_id not in context_manager.recorders:
        return {"recording": False}
    return context_manager.get_recording_status(profile_id)


@app.delete("/screenshots/{filename}")
async def delete_screenshot(filename: str, _=verify_api_key):
    """Delete a screenshot file."""
    # Security: prevent path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    deleted = await context_manager.delete_screenshot(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return {"status": "deleted"}


@app.delete("/videos/{profile_id}/{filename}")
async def delete_video(profile_id: str, filename: str, _=verify_api_key):
    """Delete a video file."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    deleted = await context_manager.delete_video(profile_id, filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "deleted"}


@app.get("/profiles/{profile_id}/videos")
async def list_videos(profile_id: str, _=verify_api_key):
    """List all video recordings for a profile."""
    videos = context_manager.get_profile_videos(profile_id)
    return {"videos": videos}


@app.get("/videos/{profile_id}/{filename}")
async def get_video(profile_id: str, filename: str, _=verify_api_key):
    """Serve a specific video file."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if profile_id not in context_manager.profile_data_dirs:
        raise HTTPException(status_code=404, detail="Profile not found")
    video_dir = context_manager.profile_data_dirs[profile_id] / "videos"
    filepath = video_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Video not found")
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
