import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Enum as SQLEnum, Text
from datetime import datetime
import enum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Default connection string for local development
# Format: postgresql+asyncpg://user:password@host:port/database
DEFAULT_DB_URL = "postgresql+asyncpg://browser_farm:browser_farm_pass@localhost:5432/browser_farm"

# Fetch from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Create the Async Engine
# pool_pre_ping=True checks connections before using them (good for reliability)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query debugging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create the Session Factory
# expire_on_commit=False is necessary for async so objects are accessible after commit
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for our ORM models
Base = declarative_base()


# ---------------------------------------------------------
# Database Models (SQLAlchemy ORM)
# ---------------------------------------------------------

class ProfileModeEnum(enum.Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    COMMAND_CENTER = "command_center"

class ProfileStatusEnum(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    CRASHED = "crashed"
    INSTALLING = "installing"


class ProfileDB(Base):
    """SQLAlchemy ORM model for the profiles table."""
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mode = Column(SQLEnum(ProfileModeEnum), default=ProfileModeEnum.AUTOMATED)
    proxy_id = Column(String, nullable=True) # Can be None

    # Browser Config
    user_agent = Column(String, nullable=True)
    timezone = Column(String, default="America/New_York")
    locale = Column(String, default="en-US")
    geolocation = Column(String, nullable=True) # Storing as JSON string or separate table, simplified here

    # Execution Config
    # We store script code as Text. For multiple scripts, we join them or use a separate table.
    # For simplicity in this iteration, we store the concatenated code or the last set.
    # Ideally, scripts would be a related table, but to align with current dict logic:
    scripts = Column(Text, default="[]") # Storing JSON list of strings
    requirements = Column(Text, default="[]") # Storing JSON list of strings

    # Resource Management
    memory_threshold_mb = Column(Integer, default=400)

    # State
    status = Column(SQLEnum(ProfileStatusEnum), default=ProfileStatusEnum.IDLE)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Profile(id={self.id}, name={self.name}, status={self.status})>"


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

async def init_db():
    """
    Initialize the database.
    Creates all tables defined in the Base metadata.
    """
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Database tables created/verified.")


async def get_db() -> AsyncSession:
    """
    Dependency function for FastAPI.
    Yields an async session and ensures it is closed after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
