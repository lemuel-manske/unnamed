import pytest

from application import OutboxDispatcher
from domain import OutboxMessage


class FakeOutbox:
    def __init__(self, message: OutboxMessage | None) -> None:
        self.message = message
        self.confirmed: list[OutboxMessage] = []
        self.rescheduled: list[tuple[OutboxMessage, float]] = []

    async def claim(self, lease_duration: float) -> OutboxMessage | None:
        return self.message

    async def confirm(self, message: OutboxMessage) -> None:
        self.confirmed.append(message)

    async def reschedule(self, message: OutboxMessage, delay: float) -> None:
        self.rescheduled.append((message, delay))


class FakePublisher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, message_id: str, envelope: bytes) -> None:
        self.published.append((message_id, envelope))

        if self.error is not None:
            raise self.error


@pytest.fixture
def message() -> OutboxMessage:
    return OutboxMessage("message-1", b'{"type":"CapturePage"}', "lease-1")


async def test_dispatcher_publishes_then_confirms_a_claimed_message(
    message: OutboxMessage,
) -> None:
    outbox = FakeOutbox(message)
    publisher = FakePublisher()
    dispatcher = OutboxDispatcher(outbox, publisher)

    assert await dispatcher.dispatch_once()

    assert publisher.published == [(message.message_id, message.envelope)]
    assert outbox.confirmed == [message]
    assert outbox.rescheduled == []


async def test_dispatcher_reschedules_a_message_when_publication_fails(
    message: OutboxMessage,
) -> None:
    outbox = FakeOutbox(message)
    publisher = FakePublisher(ConnectionError("broker unavailable"))
    dispatcher = OutboxDispatcher(outbox, publisher, retry_delay=12)

    assert await dispatcher.dispatch_once()

    assert publisher.published == [(message.message_id, message.envelope)]
    assert outbox.confirmed == []
    assert outbox.rescheduled == [(message, 12)]


async def test_dispatcher_returns_false_when_no_message_is_due() -> None:
    outbox = FakeOutbox(None)
    publisher = FakePublisher()
    dispatcher = OutboxDispatcher(outbox, publisher)

    assert not await dispatcher.dispatch_once()

    assert publisher.published == []
    assert outbox.confirmed == []
    assert outbox.rescheduled == []


async def test_dispatcher_does_not_confirm_when_persistence_confirmation_fails(
    message: OutboxMessage,
) -> None:
    class FailingOutbox(FakeOutbox):
        async def confirm(self, message: OutboxMessage) -> None:
            raise RuntimeError("DynamoDB unavailable")

    outbox = FailingOutbox(message)
    publisher = FakePublisher()
    dispatcher = OutboxDispatcher(outbox, publisher)

    with pytest.raises(RuntimeError, match="DynamoDB unavailable"):
        await dispatcher.dispatch_once()

    assert publisher.published == [(message.message_id, message.envelope)]
    assert outbox.rescheduled == []
