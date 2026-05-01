from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings

settings = get_settings()

REDIS_TIMEOUT_KWARGS = {
    "decode_responses": True,
    "socket_connect_timeout": 0.5,
    "socket_timeout": 1.0,
    "retry_on_timeout": False,
}


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, **REDIS_TIMEOUT_KWARGS)


def get_async_redis() -> AsyncRedis:
    return AsyncRedis.from_url(settings.redis_url, **REDIS_TIMEOUT_KWARGS)
