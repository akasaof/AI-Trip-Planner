
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect_to_mongo() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]


def close_mongo_connection() -> None:
    global _client
    if _client is not None:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        connect_to_mongo()
    return _db  # type: ignore[return-value]


# Collection helpers -----------------------------------------------------

def users_collection():
    return get_db()["users"]


def trips_collection():
    return get_db()["trips"]


def messages_collection():
    return get_db()["messages"]


def tool_results_collection():
    return get_db()["tool_results"]


async def ensure_indexes() -> None:
    """Create indexes used by the API's query patterns. Safe to call repeatedly."""
    await trips_collection().create_index("user_id")
    await messages_collection().create_index([("trip_id", 1), ("created_at", 1)])
    await tool_results_collection().create_index([("trip_id", 1), ("created_at", 1)])
