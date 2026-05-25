from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProfileStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    CRASHED = "crashed"
    INSTALLING = "installing"  # New status for dependency installation phase


class ProfileMode(str, Enum):
    MANUAL = "manual"               # Browser only, no script execution
    AUTOMATED = "automated"         # Standard script chain execution
    COMMAND_CENTER = "command_center" # Orchestrator profile (Singleton per server)


class ProxyConfig(BaseModel):
    id: str
    host: str
    port: int
    protocol: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None


class Account(BaseModel):
    """Account credentials for automation"""
    id: str
    platform: str
    platform_url: Optional[str] = None
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"
    banned: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None


class Geolocation(BaseModel):
    lat: float
    lng: float


class Profile(BaseModel):
    id: str
    name: str
    mode: ProfileMode = ProfileMode.AUTOMATED  # New Field
    proxy_id: str

    # Browser Configuration
    user_agent: Optional[str] = None
    timezone: str = "America/New_York"
    locale: str = "en-US"
    geolocation: Optional[Geolocation] = None

    # Script & Execution Configuration
    scripts: List[str] = []            # List of script code strings (Chain)
    requirements: List[str] = []       # List of pip packages e.g. ["pyautogui", "bs4"]

    # Resource Management
    memory_threshold_mb: int = 400

    # State
    status: ProfileStatus = ProfileStatus.IDLE
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProfileCreate(BaseModel):
    name: str
    mode: ProfileMode = ProfileMode.AUTOMATED
    proxy_id: str

    # Browser Configuration
    user_agent: Optional[str] = None
    timezone: str = "America/New_York"
    locale: str = "en-US"
    geolocation: Optional[Geolocation] = None

    # Script & Execution Configuration
    scripts: List[str] = []
    requirements: List[str] = []

    # Resource Management
    memory_threshold_mb: int = 400


class ProfileMetrics(BaseModel):
    memory_mb: int
    memory_limit_mb: int
    cpu_percent: float
    uptime_seconds: int
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0


class Screenshot(BaseModel):
    id: str
    timestamp: datetime
    url: str
    size_bytes: int


class Video(BaseModel):
    id: str
    timestamp: datetime
    url: str
    duration_seconds: int
    size_bytes: int


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str


class ServerHealth(BaseModel):
    status: str
    version: str
    max_contexts: int
    current_contexts: int
    memory_total_mb: int
    memory_used_mb: int
    memory_available_mb: int
    cpu_usage: float
    uptime_seconds: int
