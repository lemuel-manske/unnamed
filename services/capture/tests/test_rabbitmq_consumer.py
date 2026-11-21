import json

from adapters.messaging.rabbitmq.consumer import parse_delivery


def test_parse_delivery_extracts_archive_and_url_identity() -> None:
    body = json.dumps(
        {
            "messageId": "message-1",
            "correlationId": "archive-1",
            "type": "CapturePage",
            "version": 1,
            "occurredAt": "2026-11-20T12:00:00Z",
            "payload": {"archiveId": "archive-1", "urlKey": "v1-identity"},
        }
    ).encode()

    assert parse_delivery(body) == ("archive-1", "v1-identity")


def test_parse_delivery_rejects_malformed_or_unsupported_envelopes() -> None:
    assert parse_delivery(b"{") is None
    assert parse_delivery(b"[]") is None

    envelope = {
        "messageId": "message-1",
        "correlationId": "archive-1",
        "type": "CapturePage",
        "version": True,
        "occurredAt": "2026-11-20T12:00:00Z",
        "payload": {"archiveId": "archive-1", "urlKey": "url-1"},
    }

    assert parse_delivery(json.dumps(envelope).encode()) is None
