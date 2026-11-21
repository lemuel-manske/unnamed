from typing import cast

import aio_pika
import pytest

from adapters.messaging.rabbitmq.publisher import (
    CAPTURE_ROUTING_KEY,
    EXCHANGE_NAME,
    RabbitMQMessagePublisher,
)


class FakeExchange:
    def __init__(self) -> None:
        self.publications: list[tuple[object, str, bool]] = []

    async def publish(
        self,
        message: object,
        routing_key: str,
        mandatory: bool,
    ) -> None:
        self.publications.append((message, routing_key, mandatory))


class FakeChannel:
    def __init__(self) -> None:
        self.exchange = FakeExchange()
        self.declarations: list[tuple[str, object, bool]] = []
        self.is_closed = False

    async def declare_exchange(
        self,
        name: str,
        exchange_type: object,
        durable: bool,
    ) -> FakeExchange:
        self.declarations.append((name, exchange_type, durable))
        return self.exchange

    async def close(self) -> None:
        self.is_closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()
        self.channel_options: dict[str, bool] = {}

    async def channel(
        self,
        publisher_confirms: bool,
        on_return_raises: bool,
    ) -> FakeChannel:
        self.channel_options = {
            "publisher_confirms": publisher_confirms,
            "on_return_raises": on_return_raises,
        }
        return self.channel_instance


async def test_publisher_declares_durable_exchange_and_publishes_persistent_message() -> None:
    connection = FakeConnection()
    publisher = RabbitMQMessagePublisher(connection)  # type: ignore[arg-type]

    await publisher.start()
    await publisher.publish("message-1", b'{"type":"CapturePage"}')

    assert connection.channel_options == {
        "publisher_confirms": True,
        "on_return_raises": True,
    }
    assert connection.channel_instance.declarations == [
        (EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, True)
    ]

    message, routing_key, mandatory = connection.channel_instance.exchange.publications[0]
    published = cast(aio_pika.Message, message)

    assert published.message_id == "message-1"
    assert published.body == b'{"type":"CapturePage"}'
    assert published.content_type == "application/json"
    assert published.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert routing_key == CAPTURE_ROUTING_KEY
    assert mandatory

    await publisher.close()

    assert connection.channel_instance.is_closed


async def test_publisher_rejects_publication_before_startup() -> None:
    publisher = RabbitMQMessagePublisher(FakeConnection())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="has not been started"):
        await publisher.publish("message-1", b"{}")
