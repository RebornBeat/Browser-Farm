import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from datetime import datetime

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
# This is the ONLY place Base should be defined.
Base = declarative_base()


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

async def init_db():
    """
    Initialize the database.
    Creates all tables defined in the Base metadata.
    NOTE: Ensure all models (from models_db.py) are imported in server.py
    before calling this so they register on Base.
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
