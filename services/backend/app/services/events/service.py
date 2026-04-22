import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.core.redis import get_async_redis, get_redis
from app.utils.time import utcnow

logger = logging.getLogger(__name__)
EVENT_CHANNEL = "platform-events"


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    message = json.dumps(
        {
            "event": event_type,
            "timestamp": utcnow().isoformat(),
            "payload": payload,
        }
    )
    try:
        redis = get_redis()
        redis.publish(EVENT_CHANNEL, message)
        redis.close()
    except Exception as exc:  # pragma: no cover - non-critical telemetry path
        logger.warning("Failed to publish event %s: %s", event_type, exc)


async def event_stream() -> AsyncGenerator[str, None]:
    redis = get_async_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
            if message and message.get("type") == "message":
                yield f"data: {message['data']}\n\n"
            else:
                yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(EVENT_CHANNEL)
        await pubsub.close()
        await redis.close()
