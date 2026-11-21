# Capture

Capture executes page-level web captures for Castellani. Its distributed frontier remains the authority for URL admission, task ownership, retries, and crawl completion; browser execution does not schedule work independently.

## Development

> [!NOTE]
> On Linux, `certutil` from `libnss3-tools` must be available so Chromium can trust the attempt-local recorder CA without disabling TLS verification. Each capture attempt owns its recorder process, browser profile, and output directory.

Install the pinned Python toolchain and dependencies with `make install`.

Install the matching Playwright browser with `uv run playwright install chromium`.

- `make install`: download dependencies.
- `make db-up`: start isolated DynamoDB Local and RabbitMQ.
- `make db-down`: stop local dependencies.
- `make run`: start the Capture API and background worker runtime.
- `make fmt`: format and lint the Python service.
- `make test-unit`: run unit tests.
- `make test-integration`: run tests requiring DynamoDB Local.
- `make check`: run static analysis.

The local recording prototype uses pywb as an HTTP(S) recording proxy. The runtime uses a durable RabbitMQ command queue and a DynamoDB-backed transactional outbox; publisher confirms are required before an outbox record is marked as published.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `test` | AWS SDK access key |
| `AWS_SECRET_ACCESS_KEY` | `test` | AWS SDK secret key |
| `AWS_EC2_METADATA_DISABLED` | `true` | Disable EC2 metadata service |
| `DYNAMODB_ENDPOINT_URL` | `http://localhost:4566` | Optional DynamoDB-compatible endpoint |
| `RABBITMQ_URL` | `amqp://castellani:local-development-only@localhost:5672/` | Message broker connection |
