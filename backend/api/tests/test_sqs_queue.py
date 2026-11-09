import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fakes import FakeCaptureRepository

from capture_service import CaptureService
from models import GpsSample
from ports import CaptureMessage, QueueUnavailableError, RouteObject
from s3_route_store import S3RouteStore
from sqs_queue import SqsCaptureQueue, serialize_message

MESSAGE = CaptureMessage(
    capture_id="capture_abc",
    player_id="player-1",
    route_object=RouteObject(
        bucket="my-test-bucket", key="captures/player-1/capture_abc/route.json"
    ),
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


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        return {}


def test_message_has_exactly_the_proposed_fields_and_no_gps_data():
    body = json.loads(serialize_message(MESSAGE))

    assert body == {
        "schemaVersion": 1,
        "captureId": "capture_abc",
        "playerId": "player-1",
        "routeObject": {
            "bucket": "my-test-bucket",
            "key": "captures/player-1/capture_abc/route.json",
        },
    }


def test_send_calls_sqs_once_with_the_queue_url_and_the_message():
    client = FakeSqsClient()

    SqsCaptureQueue(client, "https://example.invalid/queue").send(MESSAGE)

    assert len(client.calls) == 1
    assert client.calls[0]["QueueUrl"] == "https://example.invalid/queue"
    assert json.loads(client.calls[0]["MessageBody"])["captureId"] == "capture_abc"


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


def test_service_with_both_adapters_points_the_message_at_the_saved_route():
    s3_client = FakeS3Client()
    sqs_client = FakeSqsClient()
    service = CaptureService(
        FakeCaptureRepository(),
        S3RouteStore(s3_client, "my-test-bucket"),
        SqsCaptureQueue(sqs_client, "https://example.invalid/queue"),
    )
    start = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)
    samples = [
        GpsSample(34.7025, 135.4959, start + timedelta(seconds=i), 10.0)
        for i in range(4)
    ]
    player_id = "11111111-2222-3333-4444-555555555555"

    result = service.submit(player_id, "key-0001-abcdef", samples)

    message = json.loads(sqs_client.calls[0]["MessageBody"])
    assert message["captureId"] == result.capture_id
    assert message["playerId"] == player_id
    assert message["routeObject"]["bucket"] == "my-test-bucket"
    assert message["routeObject"]["key"] == s3_client.calls[0]["Key"]
    assert len(sqs_client.calls[0]["MessageBody"]) < 1000
