import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from capture_queue import (
    CaptureJob,
    QueueUnavailableError,
    SqsCaptureQueue,
    serialize_job,
)
from errors import PAYLOAD_TOO_LARGE, ApiError
from models import GpsSample

START = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)


def make_samples(count):
    return [
        GpsSample(
            latitude=34.7025,
            longitude=135.4959,
            timestamp=START + timedelta(seconds=index),
            accuracy_meters=10.0,
        )
        for index in range(count)
    ]


def make_job(sample_count=4):
    return CaptureJob(
        capture_id="cap_abc123",
        player_id="player-sub-1",
        request_id="req-1",
        submitted_at=START,
        samples=make_samples(sample_count),
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
        return {"MessageId": "fake-message-id"}


def test_serialized_job_has_the_expected_fields():
    message = json.loads(serialize_job(make_job()))

    assert set(message) == {
        "schemaVersion",
        "captureId",
        "playerId",
        "requestId",
        "submittedAt",
        "route",
    }
    assert message["schemaVersion"] == 1
    assert message["captureId"] == "cap_abc123"
    assert message["playerId"] == "player-sub-1"
    assert message["submittedAt"] == "2026-10-23T01:00:00Z"


def test_serialized_route_uses_the_contract_field_names():
    message = json.loads(serialize_job(make_job()))

    assert len(message["route"]) == 4
    assert message["route"][1] == {
        "latitude": 34.7025,
        "longitude": 135.4959,
        "timestamp": "2026-10-23T01:00:01Z",
        "accuracyMeters": 10.0,
    }


def test_job_larger_than_the_limit_is_rejected_with_413():
    with pytest.raises(ApiError) as exc_info:
        serialize_job(make_job(), max_bytes=100)

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == PAYLOAD_TOO_LARGE


def test_a_route_of_10000_samples_does_not_fit_in_one_sqs_message():
    # This documents the open problem in docs/API_CONTRACT.md: the contract
    # allows 10,000 samples, but one SQS message holds only 256 KiB.
    with pytest.raises(ApiError) as exc_info:
        serialize_job(make_job(sample_count=10_000))

    assert exc_info.value.status_code == 413


def test_send_calls_sqs_once_with_the_queue_url_and_json_body():
    client = FakeSqsClient()
    queue = SqsCaptureQueue(client, "https://example.invalid/queue")

    queue.send(make_job())

    assert len(client.calls) == 1
    assert client.calls[0]["QueueUrl"] == "https://example.invalid/queue"
    assert json.loads(client.calls[0]["MessageBody"])["captureId"] == "cap_abc123"


def test_aws_client_error_becomes_queue_unavailable():
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "secret details"}},
        "SendMessage",
    )
    queue = SqsCaptureQueue(FakeSqsClient(error), "https://example.invalid/queue")

    with pytest.raises(QueueUnavailableError) as exc_info:
        queue.send(make_job())

    assert "secret details" not in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_connection_failure_becomes_queue_unavailable():
    error = EndpointConnectionError(endpoint_url="https://example.invalid")
    queue = SqsCaptureQueue(FakeSqsClient(error), "https://example.invalid/queue")

    with pytest.raises(QueueUnavailableError):
        queue.send(make_job())


def test_too_large_job_is_not_sent_to_sqs():
    client = FakeSqsClient()
    queue = SqsCaptureQueue(client, "https://example.invalid/queue")

    with pytest.raises(ApiError):
        queue.send(make_job(sample_count=10_000))

    assert client.calls == []
