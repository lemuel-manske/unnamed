from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import aio_pika
import boto3
from aio_pika.abc import AbstractRobustConnection

from adapters.artifacts.local import LocalArtifactStore
from adapters.browser.executor import BrowserPageExecutor
from adapters.messaging.rabbitmq.consumer import (
    QUEUE_NAME,
    RabbitMQPageTaskConsumer,
)
from adapters.messaging.rabbitmq.publisher import RabbitMQMessagePublisher
from adapters.persistence.dynamodb.alloc import DynamoDBCaptureAllocator
from adapters.persistence.dynamodb.outbox import DynamoDBOutbox
from adapters.persistence.dynamodb.task import DynamoDBTaskRepository
from application import OutboxDispatcher
from worker import new_worker

from .config import CaptureSettings

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient

CONSUMER_START_TIMEOUT_SECONDS = 10


class CaptureRuntime:
    """Assembles and manages the Capture worker and messaging processes."""

    def __init__(self, settings: CaptureSettings) -> None:
        self.settings = settings
        self.dynamodb_client: DynamoDBClient | None = None
        self.connection: AbstractRobustConnection | None = None
        self.publisher: RabbitMQMessagePublisher | None = None
        self.consumer_task: asyncio.Task[None] | None = None
        self.dispatcher_task: asyncio.Task[None] | None = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return (
            self._ready
            and self.consumer_task is not None
            and not self.consumer_task.done()
            and self.dispatcher_task is not None
            and not self.dispatcher_task.done()
        )

    async def start(self) -> None:
        if self._ready:
            raise RuntimeError("Capture runtime has already started")

        try:
            session = boto3.Session()

            if self.settings.dynamodb_endpoint_url is None:
                dynamodb_client = session.client(
                    "dynamodb",
                    region_name=self.settings.aws_region,
                )
            else:
                dynamodb_client = session.client(
                    "dynamodb",
                    region_name=self.settings.aws_region,
                    endpoint_url=self.settings.dynamodb_endpoint_url,
                )

            self.dynamodb_client = dynamodb_client

            for table_name in (
                self.settings.frontier_table_name,
                self.settings.runs_table_name,
                self.settings.outbox_table_name,
                self.settings.browser_slots_table_name,
            ):
                await asyncio.to_thread(
                    dynamodb_client.describe_table,
                    TableName=table_name,
                )

            connection = cast(
                AbstractRobustConnection,
                await cast(Any, aio_pika).connect_robust(self.settings.rabbitmq_url),
            )
            self.connection = connection

            task_repository = DynamoDBTaskRepository(
                client=dynamodb_client,
                frontier_table_name=self.settings.frontier_table_name,
                runs_table_name=self.settings.runs_table_name,
                lease_duration=self.settings.lease_duration,
                outbox_table_name=self.settings.outbox_table_name,
            )
            allocator = DynamoDBCaptureAllocator(
                client=dynamodb_client,
                table_name=self.settings.browser_slots_table_name,
                slot_count=self.settings.browser_slot_count,
                lease_duration=self.settings.lease_duration,
            )
            worker = new_worker(
                task_repository=task_repository,
                capture_allocator=allocator,
                executor=BrowserPageExecutor(),
                artifacts=LocalArtifactStore(Path(self.settings.artifact_directory)),
            )

            publisher = RabbitMQMessagePublisher(connection)
            self.publisher = publisher
            await publisher.start()

            consumer_ready = asyncio.Event()
            consumer = RabbitMQPageTaskConsumer(worker)
            self.consumer_task = asyncio.create_task(
                consumer.run(connection, queue_name=QUEUE_NAME, ready=consumer_ready),
                name="capture-rabbitmq-consumer",
            )
            await asyncio.wait_for(
                consumer_ready.wait(),
                timeout=CONSUMER_START_TIMEOUT_SECONDS,
            )

            dispatcher = OutboxDispatcher(
                outbox=DynamoDBOutbox(
                    client=dynamodb_client,
                    table_name=self.settings.outbox_table_name,
                ),
                publisher=publisher,
                lease_duration=self.settings.outbox_lease_duration,
                retry_delay=self.settings.outbox_retry_delay,
                poll_interval=self.settings.outbox_poll_interval,
            )
            self.dispatcher_task = asyncio.create_task(
                dispatcher.run(),
                name="capture-outbox-dispatcher",
            )

            self._ready = True
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        self._ready = False

        tasks = [
            task
            for task in (self.consumer_task, self.dispatcher_task)
            if task is not None
        ]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.consumer_task = None
        self.dispatcher_task = None

        try:
            if self.publisher is not None:
                await self.publisher.close()
                self.publisher = None
        finally:
            try:
                if self.connection is not None:
                    await self.connection.close()
                    self.connection = None
            finally:
                if self.dynamodb_client is not None:
                    self.dynamodb_client.close()
                    self.dynamodb_client = None
