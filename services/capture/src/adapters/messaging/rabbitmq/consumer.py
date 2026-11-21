import asyncio
import json
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from worker.api import CaptureRunner

from .publisher import CAPTURE_ROUTING_KEY, EXCHANGE_NAME

QUEUE_NAME = "castellani.capture.page"
EXPECTED_MESSAGE_TYPE = "CapturePage"
EXPECTED_MESSAGE_VERSION = 1


def parse_delivery(body: bytes) -> tuple[str, str] | None:
    try:
        decoded: object = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(decoded, dict):
        return None

    envelope = cast(dict[str, object], decoded)

    message_id = envelope.get("messageId")
    correlation_id = envelope.get("correlationId")
    occurred_at = envelope.get("occurredAt")
    version = envelope.get("version")

    if (
        not isinstance(message_id, str)
        or not message_id
        or not isinstance(correlation_id, str)
        or not correlation_id
        or envelope.get("type") != EXPECTED_MESSAGE_TYPE
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version != EXPECTED_MESSAGE_VERSION
        or not isinstance(occurred_at, str)
        or not occurred_at
    ):
        return None

    payload = envelope.get("payload")

    if not isinstance(payload, dict):
        return None

    payload = cast(dict[str, object], payload)

    archive_id = payload.get("archiveId")
    url_key = payload.get("urlKey")

    if not isinstance(archive_id, str) or not archive_id:
        return None

    if not isinstance(url_key, str) or not url_key:
        return None

    return archive_id, url_key


class RabbitMQPageTaskConsumer:
    """Consumes CapturePage commands and delegates execution to the worker."""

    def __init__(self, page_capturer: CaptureRunner) -> None:
        self.process_page = page_capturer

    async def handle(self, message: AbstractIncomingMessage) -> None:
        delivery = parse_delivery(message.body)

        if delivery is None:
            await message.reject(requeue=False)
            return

        archive_id, url_key = delivery

        async with message.process(requeue=True):
            await self.process_page(archive_id, url_key)

    async def run(
        self,
        connection: AbstractRobustConnection,
        exchange_name: str = EXCHANGE_NAME,
        queue_name: str = QUEUE_NAME,
        routing_key: str = CAPTURE_ROUTING_KEY,
        ready: asyncio.Event | None = None,
    ) -> None:
        channel: Any = await connection.channel()
        queue: Any | None = None
        consumer_tag: str | None = None

        try:
            await channel.set_qos(prefetch_count=1)

            exchange = await channel.declare_exchange(
                exchange_name,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.bind(exchange, routing_key=routing_key)

            consumer_tag = await queue.consume(self.handle)

            if ready is not None:
                ready.set()

            await asyncio.Event().wait()
        finally:
            try:
                if queue is not None and consumer_tag is not None:
                    await queue.cancel(consumer_tag)
            finally:
                await channel.close()
