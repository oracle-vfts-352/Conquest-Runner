import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from models import GpsSample
from ports import RouteObject, StorageUnavailableError
from s3_route_store import S3RouteStore

START = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)
PLAYER = "11111111-2222-3333-4444-555555555555"
CAPTURE = "capture_0123456789abcdef0123456789abcdef"


def make_samples(count=4):
    return [
        GpsSample(
            latitude=34.7025,
            longitude=135.4959,
            timestamp=START + timedelta(seconds=index),
            accuracy_meters=10.0,
        )
        for index in range(count)
    ]


class FakeS3Client:
    """A stand-in for the boto3 S3 client. It never contacts AWS."""

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def put_object(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)
        return {}


def test_route_is_saved_under_the_expected_key():
    client = FakeS3Client()

    result = S3RouteStore(client, "my-test-bucket").put(PLAYER, CAPTURE, make_samples())

    expected_key = f"captures/{PLAYER}/{CAPTURE}/route.json"
    assert result == RouteObject(bucket="my-test-bucket", key=expected_key)
    assert len(client.calls) == 1
    assert client.calls[0]["Bucket"] == "my-test-bucket"
    assert client.calls[0]["Key"] == expected_key


def test_saved_document_uses_the_contract_field_names():
    client = FakeS3Client()

    S3RouteStore(client, "b").put(PLAYER, CAPTURE, make_samples())

    document = json.loads(client.calls[0]["Body"])
    assert document["schemaVersion"] == 1
    assert len(document["route"]) == 4
    assert document["route"][1] == {
        "latitude": 34.7025,
        "longitude": 135.4959,
        "timestamp": "2026-10-23T01:00:01Z",
        "accuracyMeters": 10.0,
    }


def test_object_is_json_and_encrypted():
    client = FakeS3Client()

    S3RouteStore(client, "b").put(PLAYER, CAPTURE, make_samples())

    assert client.calls[0]["ContentType"] == "application/json"
    assert client.calls[0]["ServerSideEncryption"] == "AES256"


def test_saving_again_uses_the_same_key():
    client = FakeS3Client()
    store = S3RouteStore(client, "b")

    first = store.put(PLAYER, CAPTURE, make_samples())
    second = store.put(PLAYER, CAPTURE, make_samples())

    assert first == second
    assert client.calls[0]["Key"] == client.calls[1]["Key"]


def test_aws_error_becomes_storage_unavailable_without_leaking_details():
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "secret details"}}, "PutObject"
    )
    store = S3RouteStore(FakeS3Client(error), "b")

    with pytest.raises(StorageUnavailableError) as exc_info:
        store.put(PLAYER, CAPTURE, make_samples())

    assert "secret details" not in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_connection_failure_becomes_storage_unavailable():
    error = EndpointConnectionError(endpoint_url="https://example.invalid")
    store = S3RouteStore(FakeS3Client(error), "b")

    with pytest.raises(StorageUnavailableError):
        store.put(PLAYER, CAPTURE, make_samples())


@pytest.mark.parametrize(
    "player_id", ["", "a/b", "../x", "a b", "player\n", "x" * 129, "a.b"]
)
def test_unsafe_player_id_is_refused_before_any_upload(player_id):
    client = FakeS3Client()

    with pytest.raises(ValueError, match="Unsupported identifier"):
        S3RouteStore(client, "b").put(player_id, CAPTURE, make_samples())

    assert client.calls == []


def test_unsafe_capture_id_is_refused_before_any_upload():
    client = FakeS3Client()

    with pytest.raises(ValueError):
        S3RouteStore(client, "b").put(PLAYER, "capture/../x", make_samples())

    assert client.calls == []
