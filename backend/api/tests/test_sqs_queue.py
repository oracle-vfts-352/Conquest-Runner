import json

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from errors import INVALID_REQUEST, ApiError
from ports import CaptureMessage, QueueUnavailableError, RoutePayload
from sqs_queue import SqsCaptureQueue, serialize_message

MESSAGE = CaptureMessage(
    capture_id="capture_abc",
    player_id="player-1",
    route=RoutePayload(encoding="gzip+base64", data="H4sIAAAAAAAC"),
)


class FakeSqsClient:
    """A stand-in for the boto3 SQS client. It never contacts AWS."""

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def send_message(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return {"MessageId": "fake-id"}


def test_message_has_exactly_the_proposed_fields():
    body = json.loads(serialize_message(MESSAGE))

    assert body == {
        "schemaVersion": 1,
        "captureId": "capture_abc",
        "playerId": "player-1",
        "route": {"encoding": "gzip+base64", "data": "H4sIAAAAAAAC"},
    }


def test_send_calls_sqs_once_with_the_queue_url_and_the_message():
    client = FakeSqsClient()

    SqsCaptureQueue(client, "https://example.invalid/queue").send(MESSAGE)

    assert len(client.calls) == 1
    assert client.calls[0]["QueueUrl"] == "https://example.invalid/queue"
    assert json.loads(client.calls[0]["MessageBody"])["captureId"] == "capture_abc"


def test_message_over_the_hard_limit_is_rejected_with_413():
    with pytest.raises(ApiError) as exc_info:
        serialize_message(MESSAGE, max_bytes=50)

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == INVALID_REQUEST


def test_message_exactly_at_the_limit_is_accepted():
    size = len(serialize_message(MESSAGE).encode("utf-8"))

    assert serialize_message(MESSAGE, max_bytes=size) == serialize_message(MESSAGE)
    with pytest.raises(ApiError):
        serialize_message(MESSAGE, max_bytes=size - 1)


def test_too_large_message_is_never_sent_to_sqs():
    client = FakeSqsClient()
    huge = CaptureMessage(
        "capture_abc", "player-1", RoutePayload("gzip+base64", "A" * 1_100_000)
    )

    with pytest.raises(ApiError) as exc_info:
        SqsCaptureQueue(client, "https://example.invalid/queue").send(huge)

    assert exc_info.value.status_code == 413
    assert client.calls == []


def test_aws_error_becomes_queue_unavailable_without_leaking_details():
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "secret details"}}, "SendMessage"
    )
    queue = SqsCaptureQueue(FakeSqsClient(error), "https://example.invalid/queue")

    with pytest.raises(QueueUnavailableError) as exc_info:
        queue.send(MESSAGE)

    assert "secret details" not in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_connection_failure_becomes_queue_unavailable():
    error = EndpointConnectionError(endpoint_url="https://example.invalid")
    queue = SqsCaptureQueue(FakeSqsClient(error), "https://example.invalid/queue")

    with pytest.raises(QueueUnavailableError):
        queue.send(MESSAGE)
