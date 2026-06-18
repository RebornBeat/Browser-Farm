from sqlalchemy import Column, String, Integer, DateTime, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from .database import Base  # UPDATED: Import shared Base from database.py
import enum

# -----------------------------------------------
# Enums (Mirror Pydantic models)
# -----------------------------------------------

class ProfileStatusDB(str, enum.Enum):
    IDLE = "idle"
    INITIALIZING = "initializing" # NEW: Added for background startup
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    CRASHED = "crashed"
    INSTALLING = "installing"

class ProfileModeDB(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    COMMAND_CENTER = "command_center"

# -----------------------------------------------
# Models
# -----------------------------------------------

class DbProfile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mode = Column(Enum(ProfileModeDB), default=ProfileModeDB.AUTOMATED, nullable=False)

    # Configuration
    proxy_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timezone = Column(String, default="America/New_York")
    locale = Column(String, default="en-US")
    geolocation = Column(JSONB, nullable=True)

    # NEW: Browser Engine Selection
    browser_engine = Column(String, default="chromium", nullable=False)
    browser_version = Column(String, nullable=True)

    # NEW: Fingerprint Coherence
    os_fingerprint = Column(String, default="windows", nullable=False)
    gpu_vendor = Column(String, nullable=True)
    gpu_renderer = Column(String, nullable=True)
    hardware_concurrency = Column(Integer, default=8)
    device_memory = Column(Integer, default=8)

    # Execution Config
    scripts = Column(JSONB, default=[])
    requirements = Column(JSONB, default=[])

    # Resource Management
    memory_threshold_mb = Column(Integer, default=1500)

    # State Management
    status = Column(Enum(ProfileStatusDB), default=ProfileStatusDB.IDLE, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # NEW: Profile aging
    last_warmed = Column(DateTime(timezone=True), nullable=True)


class DbProxy(Base):
    """
    SQL Table for Proxies.
    Allows persistence of proxy configurations linked to profiles.
    """
    __tablename__ = "proxies"

    id = Column(String, primary_key=True, index=True)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String, default="http")
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)

    # Metadata
    country = Column(String, nullable=True)
    blacklisted = Column(String, default=False) # Storing as string/bool depending on dialect
    blacklisted_sites = Column(JSONB, default=[])

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Proxy(id={self.id}, host={self.host})>"


class DbAccount(Base):
    """
    SQL Table for Accounts.
    Centralized credential management for automation.
    """
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, index=True)
    platform = Column(String, nullable=False)
    platform_url = Column(String, nullable=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False) # Ideally encrypted at rest
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    # Status
    status = Column(String, default="active")
    banned = Column(String, default="false")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Account(id={self.id}, username={self.username})>"


class DbProxyHistory(Base):
    """
    Tracks usage of a specific Account on a specific Proxy for a specific Site.
    Ensures '1 Account per Site per Proxy' compliance.
    """
    __tablename__ = "proxy_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, nullable=False, index=True)
    proxy_id = Column(String, nullable=False, index=True)
    website = Column(String, nullable=False) # e.g., 'instagram.com'
    last_used = Column(DateTime(timezone=True), server_default=func.now())

    # Enforce that one account is only used on one proxy per website
    __table_args__ = (
        UniqueConstraint('account_id', 'website', name='uix_account_website'),
    )

    def __repr__(self):
        return f"<ProxyHistory(account={self.account_id}, proxy={self.proxy_id}, site={self.website})>"
