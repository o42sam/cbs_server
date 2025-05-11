# app/database/redis.py
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from typing import Optional, Dict, Any
from app.core.config import settings

# Global Redis client instance
redis_client: Optional[aioredis.Redis] = None
mock_redis_store: Dict[str, Any] = {}

class MockRedis:
    """A basic in-memory mock for Redis operations if Redis is unavailable."""
    def __init__(self):
        self._store = mock_redis_store
        print("INFO: Using MOCK Redis (in-memory dictionary)")

    async def get(self, name: str) -> Optional[bytes]:
        value = self._store.get(name)
        return value.encode() if isinstance(value, str) else value

    async def set(self, name: str, value: Any, ex: Optional[int] = None, px: Optional[int] = None, nx: bool = False, xx: bool = False) -> Optional[bool]:
        if nx and name in self._store:
            return False
        if xx and name not in self._store:
            return False
        self._store[name] = value
        # Note: 'ex' (expiration in seconds) is not implemented in this basic mock
        if ex:
            print(f"WARN: MockRedis SET with ex={ex} for key '{name}' - TTL not implemented in mock.")
        return True

    async def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self._store:
                del self._store[name]
                count += 1
        return count

    async def ping(self) -> bool:
        return True # Mock ping always succeeds

    async def close(self):
        print("INFO: MockRedis closed connection (no-op).")
        pass

    async def flushdb(self):
        self._store.clear()
        print("INFO: MockRedis flushed database.")
        return True


async def init_redis():
    """Initializes the Redis connection or sets up a mock."""
    global redis_client
    if settings.REDIS_URL:
        try:
            redis_client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await redis_client.ping()
            settings.REDIS_AVAILABLE = True
            print("INFO: Successfully connected to Redis.")
        except RedisConnectionError as e:
            print(f"WARNING: Could not connect to Redis at {settings.REDIS_URL}. Error: {e}")
            print("INFO: Falling back to MOCK Redis client.")
            redis_client = MockRedis() # type: ignore
            settings.REDIS_AVAILABLE = False # Explicitly false, even if mock is "available"
        except Exception as e:
            print(f"WARNING: An unexpected error occurred during Redis initialization: {e}")
            print("INFO: Falling back to MOCK Redis client.")
            redis_client = MockRedis() # type: ignore
            settings.REDIS_AVAILABLE = False
    else:
        print("INFO: REDIS_URL not configured. Falling back to MOCK Redis client.")
        redis_client = MockRedis() # type: ignore
        settings.REDIS_AVAILABLE = False


async def close_redis():
    """Closes the Redis connection if it exists and is not the mock."""
    global redis_client
    if redis_client and settings.REDIS_AVAILABLE: # Only close real connections
        try:
            await redis_client.close()
            print("INFO: Redis connection closed.")
        except Exception as e:
            print(f"ERROR: Error closing Redis connection: {e}")
    elif redis_client and not settings.REDIS_AVAILABLE and hasattr(redis_client, 'close'): # Mock might have close
        await redis_client.close()


# You can add other Redis utility functions here if needed, e.g.:
async def get_redis_value(key: str) -> Optional[str]:
    if not redis_client:
        print("WARN: Redis client not initialized, cannot get value.")
        return None
    return await redis_client.get(key)

async def set_redis_value(key: str, value: str, expire_seconds: Optional[int] = None):
    if not redis_client:
        print("WARN: Redis client not initialized, cannot set value.")
        return
    await redis_client.set(key, value, ex=expire_seconds)