import base64
import json
import logging

import pytest
from fakes import FakeCaptureQueue, FakeCaptureRepository, FakeRouteStore

from capture_service import CaptureService
from http_api import handle_request

KEY = "key-0001-abcdef"
SECRET_TEXT = "private-details"


def make_route(count=4, latitude=34.7025):
    return [
        {
            "latitude": latitude,
            "longitude": 135.4959,
            "timestamp": f"2026-10-23T01:00:{second:02d}Z",
            "accuracyMeters": 10.0,
        }
        for second in range(count)
    ]


def make_event(
    method="POST",
    path="/api/v1/captures",
    body="default",
    sub="player-1",
    key=KEY,
    headers=None,
    base64_body=False,
):
    if body == "default":
        body = {"route": make_route()}

    event = {
        "version": "2.0",
        "rawPath": path,
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "requestId": "req-1",
            "http": {"method": method, "path": path},
        },
    }
    if sub is not None:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": {"sub": sub}}}
    if key is not None:
        event["headers"]["idempotency-key"] = key
    if headers:
        event["headers"].update(headers)
    if body is not None:
        raw = body if isinstance(body, str) else json.dumps(body)
        if base64_body:
            raw = base64.b64encode(raw.encode()).decode()
            event["isBase64Encoded"] = True
        event["body"] = raw
    return event


def body_of(response):
    return json.loads(response["body"])


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
    return CaptureService(repository, route_store, queue)


def assert_error(response, status_code, code):
    assert response["statusCode"] == status_code
    assert set(body_of(response)) == {"error"}
    assert body_of(response)["error"]["code"] == code
    assert isinstance(body_of(response)["error"]["message"], str)


# ---------- POST /api/v1/captures: success ----------


def test_valid_submission_returns_202_with_the_contract_fields(service, queue):
    response = handle_request(make_event(), service)

    body = body_of(response)
    assert response["statusCode"] == 202
    assert set(body) == {"captureId", "status", "statusUrl"}
    assert body["status"] == "PENDING"
    assert body["statusUrl"] == f"/api/v1/captures/{body['captureId']}"
    assert len(queue.messages) == 1


def test_response_is_json_and_not_cached(service):
    response = handle_request(make_event(), service)

    assert response["headers"]["Content-Type"] == "application/json"
    assert response["headers"]["Cache-Control"] == "no-store"


def test_retry_with_the_same_key_returns_200_and_does_not_queue_again(service, queue):
    first = body_of(handle_request(make_event(), service))
    retry = handle_request(make_event(), service)

    assert retry["statusCode"] == 200
    assert body_of(retry)["captureId"] == first["captureId"]
    assert len(queue.messages) == 1


def test_header_name_is_case_insensitive(service):
    event = make_event(key=None, headers={"Idempotency-Key": KEY})

    assert handle_request(event, service)["statusCode"] == 202


def test_base64_encoded_body_is_accepted(service):
    response = handle_request(make_event(base64_body=True), service)

    assert response["statusCode"] == 202


# ---------- identity ----------


def test_player_comes_from_the_verified_claims_not_from_the_request(service, queue):
    event = make_event(sub="real-player", headers={"x-player-id": "attacker"})

    handle_request(event, service)

    assert queue.messages[0].player_id == "real-player"


def test_player_id_in_the_body_is_rejected(service, queue, route_store):
    body = {"route": make_route(), "playerId": "attacker"}

    response = handle_request(make_event(body=body), service)

    assert_error(response, 400, "INVALID_REQUEST")
    assert queue.messages == []
    assert route_store.put_count == 0


@pytest.mark.parametrize("sub", [None, "", "   "])
def test_missing_identity_returns_401_and_stores_nothing(
    service, queue, route_store, sub
):
    response = handle_request(make_event(sub=sub), service)

    assert_error(response, 401, "UNAUTHORIZED")
    assert queue.messages == []
    assert route_store.put_count == 0


def test_identity_that_is_not_a_string_returns_401(service):
    event = make_event()
    event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"] = 12345

    assert_error(handle_request(event, service), 401, "UNAUTHORIZED")


def test_authentication_is_checked_before_the_body(service):
    response = handle_request(make_event(sub=None, body="not json"), service)

    assert response["statusCode"] == 401


# ---------- Idempotency-Key header ----------


def test_missing_idempotency_key_returns_400(service, queue):
    response = handle_request(make_event(key=None), service)

    assert_error(response, 400, "INVALID_REQUEST")
    assert "Idempotency-Key" in body_of(response)["error"]["message"]
    assert queue.messages == []


@pytest.mark.parametrize(
    "key", ["short", "x" * 129, "has space 123", "bad/char/123", "key-0001\n"]
)
def test_invalid_idempotency_key_returns_400(service, key):
    assert_error(handle_request(make_event(key=key), service), 400, "INVALID_REQUEST")


# ---------- body problems ----------


@pytest.mark.parametrize(
    "body", [None, "", "not json", "{", "[1, 2, 3]", '"text"', "null", "123"]
)
def test_unusable_body_returns_400(service, queue, body):
    response = handle_request(make_event(body=body), service)

    assert_error(response, 400, "INVALID_REQUEST")
    assert queue.messages == []


def test_invalid_base64_body_returns_400(service):
    event = make_event(body="!!! not base64 !!!")
    event["isBase64Encoded"] = True

    assert_error(handle_request(event, service), 400, "INVALID_REQUEST")


def test_deeply_nested_body_returns_400_instead_of_crashing(service):
    nested = "[" * 100_000 + "]" * 100_000

    assert_error(
        handle_request(make_event(body=nested), service), 400, "INVALID_REQUEST"
    )


def test_body_over_the_size_limit_returns_413(service, queue):
    response = handle_request(make_event(), service, max_body_bytes=100)

    assert_error(response, 413, "INVALID_REQUEST")
    assert queue.messages == []


def test_invalid_route_data_returns_400_and_names_the_field(service, queue):
    route = make_route()
    route[2]["latitude"] = 200

    response = handle_request(make_event(body={"route": route}), service)

    assert_error(response, 400, "INVALID_REQUEST")
    assert "route[2].latitude" in body_of(response)["error"]["message"]
    assert queue.messages == []


# ---------- failures behind the service ----------


def test_queue_failure_returns_503_and_never_202(service, queue):
    queue.fail = True

    response = handle_request(make_event(), service)

    assert_error(response, 503, "INTERNAL_ERROR")


def test_retry_after_a_queue_failure_succeeds(service, queue):
    queue.fail = True
    handle_request(make_event(), service)
    queue.fail = False

    response = handle_request(make_event(), service)

    assert response["statusCode"] == 202
    assert len(queue.messages) == 1


def test_same_key_with_a_different_route_returns_409(service):
    handle_request(make_event(), service)

    other = make_event(body={"route": make_route(latitude=35.0)})

    assert_error(handle_request(other, service), 409, "IDEMPOTENCY_KEY_CONFLICT")


class ExplodingService:
    def submit(self, *args, **kwargs):
        raise RuntimeError(SECRET_TEXT)

    def get_status(self, *args, **kwargs):
        raise RuntimeError(SECRET_TEXT)


def test_unexpected_error_returns_a_generic_500_and_leaks_nothing(caplog):
    caplog.set_level(logging.INFO)

    response = handle_request(make_event(), ExplodingService())

    assert_error(response, 500, "INTERNAL_ERROR")
    assert SECRET_TEXT not in response["body"]
    assert "Traceback" not in response["body"]
    assert "RuntimeError" in caplog.text
    assert SECRET_TEXT not in caplog.text


# ---------- GET /api/v1/captures/{captureId} ----------


def test_status_of_own_capture_returns_200(service):
    created = body_of(handle_request(make_event(), service))

    response = handle_request(
        make_event(
            method="GET",
            path=f"/api/v1/captures/{created['captureId']}",
            body=None,
            key=None,
        ),
        service,
    )

    body = body_of(response)
    assert response["statusCode"] == 200
    assert body["captureId"] == created["captureId"]
    assert body["status"] == "PENDING"
    assert set(body) == {"captureId", "status", "createdAt", "updatedAt"}


def test_status_of_another_players_capture_returns_404(service):
    created = body_of(handle_request(make_event(sub="player-1"), service))

    response = handle_request(
        make_event(
            method="GET",
            path=f"/api/v1/captures/{created['captureId']}",
            body=None,
            key=None,
            sub="player-2",
        ),
        service,
    )

    assert_error(response, 404, "CAPTURE_NOT_FOUND")


def test_status_without_identity_returns_401(service):
    event = make_event(
        method="GET", path="/api/v1/captures/capture_x", body=None, key=None, sub=None
    )

    assert_error(handle_request(event, service), 401, "UNAUTHORIZED")


def test_status_of_unknown_capture_returns_404(service):
    event = make_event(
        method="GET", path="/api/v1/captures/capture_missing", body=None, key=None
    )

    assert_error(handle_request(event, service), 404, "CAPTURE_NOT_FOUND")


# ---------- other routes ----------


def test_health_returns_healthy_without_authentication(service):
    event = make_event(
        method="GET", path="/api/v1/health", body=None, key=None, sub=None
    )

    response = handle_request(event, service)

    assert response["statusCode"] == 200
    assert body_of(response) == {"status": "healthy"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/unknown"),
        ("DELETE", "/api/v1/captures"),
        ("GET", "/api/v1/captures/bad id"),
        ("GET", "/api/v1/captures/a/b"),
        ("POST", "/api/v1/health"),
    ],
)
def test_unknown_routes_return_404(service, method, path):
    event = make_event(method=method, path=path, body=None, key=None)

    assert_error(handle_request(event, service), 404, "NOT_FOUND")


def test_event_without_a_path_returns_404(service):
    assert_error(handle_request({}, service), 404, "NOT_FOUND")


# ---------- logging ----------


def test_logs_never_contain_gps_data(service, caplog):
    caplog.set_level(logging.DEBUG)

    handle_request(make_event(), service)

    assert caplog.text != ""
    assert "34.7025" not in caplog.text
    assert "135.4959" not in caplog.text
