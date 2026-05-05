"""
Database configuration and models for the document upload service.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, func, text
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class User(Base):
    """User model matching the existing database schema - only authentication columns."""
    __tablename__ = "User"  # Note: capitalized to match existing table
    
    # Primary key (read-only, for identification)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Authentication columns - these are the ONLY columns we're allowed to modify
    jwtToken: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    webhookApiKey: Mapped[Optional[str]] = mapped_column(String, nullable=True) 
    webhookSecretKey: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Note: We intentionally don't define other columns to avoid accidental modifications
    # The existing table has many other columns that we must not interact with


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        # Convert postgresql:// to postgresql+asyncpg:// for async support
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL query logging
            pool_pre_ping=True,
            pool_recycle=300
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def get_session(self) -> AsyncSession:
        """Get an async database session."""
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections."""
        await self.engine.dispose()
    
    async def test_connection(self) -> bool:
        """Test database connection."""
        try:
            async with self.async_session_maker() as session:
                await session.execute(text("SELECT 1"))
                logger.info("Database connection successful")
                return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global db_manager
    if db_manager is None:
        raise RuntimeError("Database manager not initialized. Call init_database() first.")
    return db_manager


def init_database(database_url: str) -> DatabaseManager:
    """Initialize the global database manager."""
    global db_manager
    db_manager = DatabaseManager(database_url)
    return db_manager


async def get_db_session():
    """Dependency to get database session for FastAPI."""
    db = get_database_manager()
    async for session in db.get_session():
        yield session