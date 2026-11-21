import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureSettings:
    """Runtime configuration for one Capture service process."""

    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str | None = None
    rabbitmq_url: str = "amqp://castellani:local-development-only@localhost:5672/"
    frontier_table_name: str = "capture_frontier"
    runs_table_name: str = "capture_runs"
    outbox_table_name: str = "capture_outbox"
    browser_slots_table_name: str = "capture_browser_slots"
    browser_slot_count: int = 10
    lease_duration: float = 60
    outbox_lease_duration: float = 30
    outbox_retry_delay: float = 5
    outbox_poll_interval: float = 0.5
    artifact_directory: str = "/tmp/castellani/capture"

    @classmethod
    def from_environment(cls) -> "CaptureSettings":
        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL") or None,
            rabbitmq_url=os.getenv(
                "RABBITMQ_URL",
                "amqp://castellani:local-development-only@localhost:5672/",
            ),
            frontier_table_name=os.getenv("CAPTURE_FRONTIER_TABLE", "capture_frontier"),
            runs_table_name=os.getenv("CAPTURE_RUNS_TABLE", "capture_runs"),
            outbox_table_name=os.getenv("CAPTURE_OUTBOX_TABLE", "capture_outbox"),
            browser_slots_table_name=os.getenv(
                "CAPTURE_BROWSER_SLOTS_TABLE",
                "capture_browser_slots",
            ),
            browser_slot_count=_positive_int("CAPTURE_BROWSER_SLOT_COUNT", 10),
            lease_duration=_positive_float("CAPTURE_LEASE_DURATION_SECONDS", 60),
            outbox_lease_duration=_positive_float("CAPTURE_OUTBOX_LEASE_SECONDS", 30),
            outbox_retry_delay=_positive_float("CAPTURE_OUTBOX_RETRY_SECONDS", 5),
            outbox_poll_interval=_positive_float("CAPTURE_OUTBOX_POLL_SECONDS", 0.5),
            artifact_directory=os.getenv(
                "CAPTURE_ARTIFACT_DIRECTORY",
                "/tmp/castellani/capture",
            ),
        )


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))

    if value < 1:
        raise ValueError(f"{name} must be positive")

    return value


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))

    if value <= 0:
        raise ValueError(f"{name} must be positive")

    return value
