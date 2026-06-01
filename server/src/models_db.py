from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# -----------------------------------------------
# Enums (Mirror Pydantic models)
# -----------------------------------------------

class ProfileStatusDB(str, enum.Enum):
    IDLE = "idle"
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

class ProfileModel(Base):
    """
    SQL Table for Profiles.
    Replaces the in-memory 'profiles' dictionary.
    """
    __tablename__ = "profiles"

    # Primary Key (Matches the generated ID from server.py)
    id = Column(String, primary_key=True, index=True)

    # Core Info
    name = Column(String, nullable=False)
    mode = Column(Enum(ProfileModeDB), default=ProfileModeDB.AUTOMATED, nullable=False)

    # Configuration
    proxy_id = Column(String, nullable=True) # Optional: ID of the proxy
    user_agent = Column(String, nullable=True)
    timezone = Column(String, default="America/New_York")
    locale = Column(String, default="en-US")
    geolocation = Column(JSONB, nullable=True) # Stores {"lat": float, "lng": float}

    # Execution Config (Stored as JSONB arrays)
    scripts = Column(JSONB, default=list)       # List of script code strings
    requirements = Column(JSONB, default=list)  # List of pip package strings

    # Resource Management
    memory_threshold_mb = Column(Integer, default=400)

    # State Management
    status = Column(Enum(ProfileStatusDB), default=ProfileStatusDB.IDLE, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Profile(id={self.id}, name={self.name}, status={self.status})>"


class ProxyModel(Base):
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
    blacklisted = Column(String, default=False) # Storing as string/bool depending on dialect, bool is fine
    blacklisted_sites = Column(JSONB, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Proxy(id={self.id}, host={self.host})>"
