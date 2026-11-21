.PHONY: install run fmt test test-unit test-integration check db-up db-down

install:
	uv sync --all-groups


db-up:
	docker compose up -d --wait dynamodb rabbitmq

db-down:
	docker compose down


test-unit:
	uv run pytest -m "not integration"

test-integration:
	DYNAMODB_ENDPOINT_URL=http://localhost:8000 uv run pytest -m integration

test: test-unit test-integration


fmt:
	uv run ruff format .
	uv run ruff check --fix .

check:
	uv run ruff check .
	uv run pyright


run:
	PYTHONPATH=src uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
