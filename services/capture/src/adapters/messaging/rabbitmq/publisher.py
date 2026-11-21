from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustConnection

EXCHANGE_NAME = "castellani.capture"
CAPTURE_ROUTING_KEY = "CapturePage"


class RabbitMQMessagePublisher:
    """Publishes persistent Capture command envelopes with broker confirms."""

    def __init__(
        self,
        connection: AbstractRobustConnection,
        exchange_name: str = EXCHANGE_NAME,
    ) -> None:
        self.connection = connection
        self.exchange_name = exchange_name
        self.channel: Any | None = None
        self.exchange: Any | None = None

    async def start(self) -> None:
        self.channel = await self.connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

    async def publish(self, message_id: str, envelope: bytes) -> None:
        if self.exchange is None:
            raise RuntimeError("RabbitMQ publisher has not been started")

        message = aio_pika.Message(
            body=envelope,
            message_id=message_id,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.exchange.publish(
            message,
            routing_key=CAPTURE_ROUTING_KEY,
            mandatory=True,
        )

    async def close(self) -> None:
        if self.channel is not None and not self.channel.is_closed:
            await self.channel.close()

        self.channel = None
        self.exchange = None
