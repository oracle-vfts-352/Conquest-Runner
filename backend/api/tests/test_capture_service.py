from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeCaptureQueue, FakeCaptureRepository, FakeRouteStore

from capture_service import CaptureService, derive_capture_id
from errors import (
    CAPTURE_NOT_FOUND,
    IDEMPOTENCY_KEY_CONFLICT,
    INTERNAL_ERROR,
    ApiError,
)
from models import GpsSample
from ports import (
    FAILED,
    PENDING,
    PROCESSING,
    RECEIVED,
    REJECTED,
    SUCCEEDED,
    CaptureRecord,
)

START = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)
PLAYER = "player-1"
KEY = "key-0001-abcdef"


def make_samples(count=4, latitude=34.7025):
    return [
        GpsSample(
            latitude=latitude,
            longitude=135.4959,
            timestamp=START + timedelta(seconds=index),
            accuracy_meters=10.0,
        )
        for index in range(count)
    ]


@pytest.fixture
def repository():
    return FakeCaptureRepository()


@pytest.fixture
def route_store():
    return FakeRouteStore()


@pytest.fixture
def queue():
    return FakeCaptureQueue()


@pytest.fixture
def service(repository, route_store, queue):
    return CaptureService(repository, route_store, queue, clock=lambda: START)


def assert_unavailable(exc_info):
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == INTERNAL_ERROR


# ---------- capture ID ----------


def test_capture_id_is_the_same_for_the_same_player_and_key():
    assert derive_capture_id(PLAYER, KEY) == derive_capture_id(PLAYER, KEY)
    assert derive_capture_id(PLAYER, KEY).startswith("capture_")


def test_capture_id_differs_between_players_and_between_keys():
    assert derive_capture_id("player-1", KEY) != derive_capture_id("player-2", KEY)
    assert derive_capture_id(PLAYER, "key-aaaaaaaa") != derive_capture_id(
        PLAYER, "key-bbbbbbbb"
    )


# ---------- submit: normal flow ----------


def test_first_submit_is_accepted_and_queued(service, repository, route_store, queue):
    result = service.submit(PLAYER, KEY, make_samples())

    assert result.status == PENDING
    assert result.already_accepted is False
    assert result.capture_id == derive_capture_id(PLAYER, KEY)
    assert repository.records[(PLAYER, result.capture_id)].status == PENDING
    assert route_store.put_count == 1
    assert len(queue.messages) == 1


def test_queue_message_has_the_callers_identity_and_the_prepared_route(service, queue):
    result = service.submit(PLAYER, KEY, make_samples())

    message = queue.messages[0]
    assert message.capture_id == result.capture_id
    assert message.player_id == PLAYER
    assert message.route.data == f"{PLAYER}/{result.capture_id}"


# ---------- submit: retries and idempotency ----------


def test_retry_after_success_does_not_create_a_second_capture(
    service, route_store, queue
):
    first = service.submit(PLAYER, KEY, make_samples())
    second = service.submit(PLAYER, KEY, make_samples())

    assert second.capture_id == first.capture_id
    assert second.already_accepted is True
    assert second.status == PENDING
    assert len(queue.messages) == 1
    assert route_store.put_count == 1


def test_same_key_with_a_different_route_is_a_conflict(service, queue):
    service.submit(PLAYER, KEY, make_samples())

    with pytest.raises(ApiError) as exc_info:
        service.submit(PLAYER, KEY, make_samples(latitude=35.0))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == IDEMPOTENCY_KEY_CONFLICT
    assert len(queue.messages) == 1


def test_two_players_can_use_the_same_key(service, queue):
    first = service.submit("player-1", KEY, make_samples())
    second = service.submit("player-2", KEY, make_samples())

    assert first.capture_id != second.capture_id
    assert len(queue.messages) == 2


def test_retry_does_not_overwrite_progress_made_by_the_worker(
    service, repository, queue
):
    first = service.submit(PLAYER, KEY, make_samples())
    record = repository.records[(PLAYER, first.capture_id)]
    repository.set_record(replace(record, status=PROCESSING))

    retry = service.submit(PLAYER, KEY, make_samples())

    assert retry.already_accepted is True
    assert retry.status == PROCESSING
    assert len(queue.messages) == 1


# ---------- submit: failures and recovery ----------


def test_queue_failure_is_not_reported_as_accepted_and_a_retry_recovers(
    service, repository, queue
):
    queue.fail = True
    with pytest.raises(ApiError) as exc_info:
        service.submit(PLAYER, KEY, make_samples())

    assert_unavailable(exc_info)
    assert queue.messages == []
    capture_id = derive_capture_id(PLAYER, KEY)
    assert repository.records[(PLAYER, capture_id)].status == RECEIVED

    queue.fail = False
    retry = service.submit(PLAYER, KEY, make_samples())

    assert retry.status == PENDING
    assert retry.already_accepted is False
    assert len(queue.messages) == 1
    assert repository.records[(PLAYER, capture_id)].status == PENDING


def test_route_store_failure_does_not_reach_the_queue_and_a_retry_recovers(
    service, route_store, queue
):
    route_store.fail = True
    with pytest.raises(ApiError) as exc_info:
        service.submit(PLAYER, KEY, make_samples())

    assert_unavailable(exc_info)
    assert queue.messages == []

    route_store.fail = False
    assert service.submit(PLAYER, KEY, make_samples()).status == PENDING
    assert len(queue.messages) == 1


def test_database_failure_stores_and_sends_nothing(
    service, repository, route_store, queue
):
    repository.fail_create = True
    with pytest.raises(ApiError) as exc_info:
        service.submit(PLAYER, KEY, make_samples())

    assert_unavailable(exc_info)
    assert route_store.put_count == 0
    assert queue.messages == []


def test_failure_after_queueing_sends_a_duplicate_message_on_retry(
    service, repository, queue
):
    # The worker must ignore duplicate messages with the same captureId.
    repository.fail_mark_pending = True
    with pytest.raises(ApiError) as exc_info:
        service.submit(PLAYER, KEY, make_samples())
    assert_unavailable(exc_info)
    assert len(queue.messages) == 1

    repository.fail_mark_pending = False
    retry = service.submit(PLAYER, KEY, make_samples())

    assert retry.status == PENDING
    assert len(queue.messages) == 2
    assert queue.messages[0].capture_id == queue.messages[1].capture_id


# ---------- get_status ----------


def put_record(repository, capture_id="capture_x", player=PLAYER, **overrides):
    record = CaptureRecord(
        capture_id=capture_id,
        player_id=player,
        request_hash="hash",
        status=PENDING,
        created_at=START,
        updated_at=START + timedelta(seconds=5),
    )
    repository.set_record(replace(record, **overrides))


def test_pending_status_has_exactly_the_contract_fields(service, repository):
    put_record(repository)

    assert service.get_status(PLAYER, "capture_x") == {
        "captureId": "capture_x",
        "status": "PENDING",
        "createdAt": "2026-10-23T01:00:00Z",
        "updatedAt": "2026-10-23T01:00:05Z",
    }


def test_succeeded_status_includes_the_result(service, repository):
    result = {"capturedAreaM2": 1250.5, "totalOwnedAreaM2": 8500.0}
    put_record(repository, status=SUCCEEDED, result=result)

    body = service.get_status(PLAYER, "capture_x")

    assert body["status"] == "SUCCEEDED"
    assert body["result"] == result
    assert "error" not in body


@pytest.mark.parametrize("status", [REJECTED, FAILED])
def test_rejected_and_failed_statuses_include_the_error(service, repository, status):
    error = {"code": "LOOP_NOT_CLOSED", "message": "The route is not a closed loop."}
    put_record(repository, status=status, error=error)

    body = service.get_status(PLAYER, "capture_x")

    assert body["status"] == status
    assert body["error"] == error
    assert "result" not in body


def test_unknown_capture_is_not_found(service):
    with pytest.raises(ApiError) as exc_info:
        service.get_status(PLAYER, "capture_missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == CAPTURE_NOT_FOUND


def test_another_players_capture_looks_the_same_as_a_missing_one(service, repository):
    put_record(repository, player="someone-else")

    with pytest.raises(ApiError) as exc_info:
        service.get_status(PLAYER, "capture_x")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == CAPTURE_NOT_FOUND


def test_capture_that_was_never_queued_is_not_visible(service, repository):
    put_record(repository, status=RECEIVED)

    with pytest.raises(ApiError) as exc_info:
        service.get_status(PLAYER, "capture_x")

    assert exc_info.value.status_code == 404


def test_database_failure_while_reading_status_returns_503(service, repository):
    repository.fail_get = True

    with pytest.raises(ApiError) as exc_info:
        service.get_status(PLAYER, "capture_x")

    assert_unavailable(exc_info)
