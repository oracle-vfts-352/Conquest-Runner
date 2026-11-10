import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from capture_service import CaptureService, derive_capture_id
from dynamodb_repository import DynamoDbCaptureRepository
from models import GpsSample
from ports import (
    PENDING,
    RECEIVED,
    SUCCEEDED,
    CaptureRecord,
    RoutePayload,
    StorageUnavailableError,
)

START = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)
PLAYER = "11111111-2222-3333-4444-555555555555"
CAPTURE = "capture_0123456789abcdef0123456789abcdef"
TABLE = "my-test-table"


def make_record(**overrides):
    values = {
        "capture_id": CAPTURE,
        "player_id": PLAYER,
        "request_hash": "hash-1",
        "status": RECEIVED,
        "created_at": START,
        "updated_at": START,
    }
    values.update(overrides)
    return CaptureRecord(**values)


def condition_failed(operation):
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
        operation,
    )


def other_error(operation):
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "secret details"}},
        operation,
    )


class FakeDynamoClient:
    """A stand-in for the boto3 DynamoDB client. It never contacts AWS.

    It only understands the exact conditions this repository uses, and it
    fails loudly on anything else, so a changed expression is not silently
    accepted by the tests.
    """

    def __init__(self, error=None):
        self.items = {}
        self.error = error
        self.calls = []

    def _fail_if_needed(self):
        if self.error is not None:
            raise self.error

    @staticmethod
    def _id(key):
        return (key["pk"]["S"], key["sk"]["S"])

    def get_item(self, **kwargs):
        self.calls.append(("get_item", kwargs))
        self._fail_if_needed()
        item = self.items.get(self._id(kwargs["Key"]))
        return {"Item": item} if item is not None else {}

    def put_item(self, **kwargs):
        self.calls.append(("put_item", kwargs))
        self._fail_if_needed()
        assert kwargs["ConditionExpression"] == "attribute_not_exists(pk)"
        key = self._id(kwargs["Item"])
        if key in self.items:
            raise condition_failed("PutItem")
        self.items[key] = kwargs["Item"]

    def update_item(self, **kwargs):
        self.calls.append(("update_item", kwargs))
        self._fail_if_needed()
        assert kwargs["ConditionExpression"] == "#s = :received"
        assert kwargs["UpdateExpression"] == "SET #s = :pending, updatedAt = :now"
        item = self.items.get(self._id(kwargs["Key"]))
        values = kwargs["ExpressionAttributeValues"]
        if item is None or item["status"] != values[":received"]:
            raise condition_failed("UpdateItem")
        item["status"] = values[":pending"]
        item["updatedAt"] = values[":now"]


@pytest.fixture
def client():
    return FakeDynamoClient()


@pytest.fixture
def repository(client):
    return DynamoDbCaptureRepository(client, TABLE)


# ---------- create ----------


def test_create_stores_the_expected_item(repository, client):
    assert repository.create(make_record()) is True

    method, kwargs = client.calls[0]
    assert method == "put_item"
    assert kwargs["TableName"] == TABLE
    assert kwargs["ConditionExpression"] == "attribute_not_exists(pk)"
    assert kwargs["Item"] == {
        "pk": {"S": f"PLAYER#{PLAYER}"},
        "sk": {"S": f"CAPTURE#{CAPTURE}"},
        "captureId": {"S": CAPTURE},
        "playerId": {"S": PLAYER},
        "requestHash": {"S": "hash-1"},
        "status": {"S": "RECEIVED"},
        "createdAt": {"S": "2026-10-23T01:00:00Z"},
        "updatedAt": {"S": "2026-10-23T01:00:00Z"},
    }


def test_create_returns_false_when_the_record_already_exists(repository, client):
    repository.create(make_record())

    assert repository.create(make_record(request_hash="other")) is False
    stored = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{CAPTURE}")]
    assert stored["requestHash"] == {"S": "hash-1"}


def test_create_failure_does_not_leak_aws_details():
    repository = DynamoDbCaptureRepository(
        FakeDynamoClient(other_error("PutItem")), TABLE
    )

    with pytest.raises(StorageUnavailableError) as exc_info:
        repository.create(make_record())

    assert "secret details" not in str(exc_info.value)


def test_connection_failure_becomes_storage_unavailable():
    error = EndpointConnectionError(endpoint_url="https://example.invalid")
    repository = DynamoDbCaptureRepository(FakeDynamoClient(error), TABLE)

    with pytest.raises(StorageUnavailableError):
        repository.create(make_record())
    with pytest.raises(StorageUnavailableError):
        repository.get(PLAYER, CAPTURE)
    with pytest.raises(StorageUnavailableError):
        repository.mark_pending(PLAYER, CAPTURE, START)


# ---------- get ----------


def test_get_returns_the_record_using_a_consistent_read(repository, client):
    repository.create(make_record())

    record = repository.get(PLAYER, CAPTURE)

    assert record == make_record()
    method, kwargs = client.calls[-1]
    assert method == "get_item"
    assert kwargs["ConsistentRead"] is True
    assert kwargs["Key"] == {
        "pk": {"S": f"PLAYER#{PLAYER}"},
        "sk": {"S": f"CAPTURE#{CAPTURE}"},
    }


def test_get_returns_none_when_there_is_no_record(repository):
    assert repository.get(PLAYER, CAPTURE) is None


def test_another_players_record_is_not_found(repository):
    repository.create(make_record())

    assert repository.get("someone-else", CAPTURE) is None


def test_get_converts_database_numbers_so_they_can_be_sent_as_json(repository, client):
    repository.create(make_record())
    item = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{CAPTURE}")]
    item["status"] = {"S": SUCCEEDED}
    item["result"] = {
        "M": {
            "capturedAreaM2": {"N": "12500.5"},
            "totalOwnedAreaM2": {"N": "48700"},
        }
    }

    record = repository.get(PLAYER, CAPTURE)

    assert record.result == {"capturedAreaM2": 12500.5, "totalOwnedAreaM2": 48700}
    assert json.loads(json.dumps(record.result)) == record.result


def test_get_reads_the_error_map_written_by_the_worker(repository, client):
    repository.create(make_record())
    item = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{CAPTURE}")]
    item["status"] = {"S": "REJECTED"}
    item["error"] = {
        "M": {"code": {"S": "LOOP_NOT_CLOSED"}, "message": {"S": "Not a closed loop."}}
    }

    record = repository.get(PLAYER, CAPTURE)

    assert record.error == {"code": "LOOP_NOT_CLOSED", "message": "Not a closed loop."}


@pytest.mark.parametrize(
    "damage",
    [
        {"requestHash": None},  # attribute removed
        {"status": {"N": "5"}},  # wrong type
        {"createdAt": {"S": "not a time"}},
        {"createdAt": {"S": "2026-10-23T01:00:00"}},  # no time zone
        {"result": {"S": "not a map"}},
    ],
)
def test_damaged_item_becomes_storage_unavailable(repository, client, damage):
    repository.create(make_record())
    item = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{CAPTURE}")]
    for name, value in damage.items():
        if value is None:
            del item[name]
        else:
            item[name] = value

    with pytest.raises(StorageUnavailableError):
        repository.get(PLAYER, CAPTURE)


def test_get_failure_does_not_leak_aws_details():
    repository = DynamoDbCaptureRepository(
        FakeDynamoClient(other_error("GetItem")), TABLE
    )

    with pytest.raises(StorageUnavailableError) as exc_info:
        repository.get(PLAYER, CAPTURE)

    assert "secret details" not in str(exc_info.value)


# ---------- mark_pending ----------


def test_mark_pending_changes_received_to_pending(repository):
    repository.create(make_record())
    later = START + timedelta(seconds=3)

    repository.mark_pending(PLAYER, CAPTURE, later)

    record = repository.get(PLAYER, CAPTURE)
    assert record.status == PENDING
    assert record.updated_at == later


def test_mark_pending_keeps_progress_made_by_the_worker(repository, client):
    repository.create(make_record())
    item = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{CAPTURE}")]
    item["status"] = {"S": "PROCESSING"}

    repository.mark_pending(PLAYER, CAPTURE, START + timedelta(seconds=3))

    assert repository.get(PLAYER, CAPTURE).status == "PROCESSING"


def test_mark_pending_uses_an_expression_that_avoids_the_reserved_word_status(
    repository, client
):
    repository.create(make_record())

    repository.mark_pending(PLAYER, CAPTURE, START)

    kwargs = client.calls[-1][1]
    assert kwargs["ExpressionAttributeNames"] == {"#s": "status"}
    assert "status" not in kwargs["UpdateExpression"]


def test_mark_pending_failure_does_not_leak_aws_details():
    repository = DynamoDbCaptureRepository(
        FakeDynamoClient(other_error("UpdateItem")), TABLE
    )

    with pytest.raises(StorageUnavailableError) as exc_info:
        repository.mark_pending(PLAYER, CAPTURE, START)

    assert "secret details" not in str(exc_info.value)


# ---------- together with the service ----------


class FakeRouteStore:
    def put(self, player_id, capture_id, samples):
        return RoutePayload(encoding="fake", data=f"{player_id}/{capture_id}")


class FakeQueue:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def make_samples():
    return [
        GpsSample(34.7025, 135.4959, START + timedelta(seconds=i), 10.0)
        for i in range(4)
    ]


def test_service_with_the_dynamodb_repository_submit_retry_and_status(client):
    queue = FakeQueue()
    service = CaptureService(
        DynamoDbCaptureRepository(client, TABLE),
        FakeRouteStore(),
        queue,
        clock=lambda: START,
    )

    first = service.submit(PLAYER, "key-0001-abcdef", make_samples())
    retry = service.submit(PLAYER, "key-0001-abcdef", make_samples())

    assert first.status == PENDING
    assert first.already_accepted is False
    assert retry.already_accepted is True
    assert len(queue.messages) == 1
    assert first.capture_id == derive_capture_id(PLAYER, "key-0001-abcdef")

    # The worker finishes the capture by writing to the same item.
    item = client.items[(f"PLAYER#{PLAYER}", f"CAPTURE#{first.capture_id}")]
    item["status"] = {"S": SUCCEEDED}
    item["result"] = {"M": {"capturedAreaM2": {"N": "1250.5"}}}

    body = service.get_status(PLAYER, first.capture_id)

    assert body["status"] == "SUCCEEDED"
    assert body["result"] == {"capturedAreaM2": 1250.5}
    json.dumps(body)  # must be possible to send as JSON
