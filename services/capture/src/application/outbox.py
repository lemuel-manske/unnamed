import asyncio
import logging
from typing import Protocol

from domain import OutboxRepository

logger = logging.getLogger(__name__)


class MessagePublisher(Protocol):
    """Publishes an immutable message envelope to the broker."""

    async def publish(self, message_id: str, envelope: bytes) -> None: ...


class OutboxDispatcher:
    """Delivers durable outbox messages and records their publication outcome."""

    def __init__(
        self,
        outbox: OutboxRepository,
        publisher: MessagePublisher,
        lease_duration: float = 30,
        retry_delay: float = 5,
        poll_interval: float = 0.5,
    ) -> None:
        if lease_duration <= 0:
            raise ValueError("lease_duration must be positive")

        if retry_delay <= 0:
            raise ValueError("retry_delay must be positive")

        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        self.outbox = outbox
        self.publisher = publisher
        self.lease_duration = lease_duration
        self.retry_delay = retry_delay
        self.poll_interval = poll_interval

    async def dispatch_once(self) -> bool:
        message = await self.outbox.claim(self.lease_duration)

        if message is None:
            return False

        try:
            await self.publisher.publish(message.message_id, message.envelope)
        except Exception:
            logger.exception("failed to publish outbox message %s", message.message_id)

            await self.outbox.reschedule(message, self.retry_delay)

            return True

        await self.outbox.confirm(message)

        return True

    async def run(self) -> None:
        while True:
            try:
                dispatched = await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("outbox dispatch cycle failed")
                dispatched = False

            if not dispatched:
                await asyncio.sleep(self.poll_interval)
