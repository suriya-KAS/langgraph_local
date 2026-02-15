"""
Async MongoDB connection management (Motor).

This module centralizes MongoDB connectivity for the `database/` package and
provides an AsyncIOMotorDatabase instance for async CRUD operations.
"""

from __future__ import annotations

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

from utils.logger_config import get_logger

load_dotenv()
logger = get_logger(__name__)

MONGO_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "msc-chatbot")


class AsyncDatabaseConnection:
    """Manages a shared Motor client + database handle."""

    def __init__(self) -> None:
        if not MONGO_URI:
            raise ValueError("MONGODB_URI environment variable is not set")

        # Motor uses lazy connection; we can still validate connectivity with ping.
        self.client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
        )
        self.db: AsyncIOMotorDatabase = self.client[DATABASE_NAME]

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    def close(self) -> None:
        if self.client:
            self.client.close()


_async_db_connection: Optional[AsyncDatabaseConnection] = None


async def get_async_database() -> AsyncIOMotorDatabase:
    """Get or create the shared Motor database handle."""
    global _async_db_connection
    if _async_db_connection is None:
        _async_db_connection = AsyncDatabaseConnection()
        await _async_db_connection.ping()
        logger.info(f"✓ Connected to MongoDB database (async): {DATABASE_NAME}")
    return _async_db_connection.db


def close_async_database() -> None:
    """Close the shared Motor client."""
    global _async_db_connection
    if _async_db_connection is not None:
        _async_db_connection.close()
        _async_db_connection = None

