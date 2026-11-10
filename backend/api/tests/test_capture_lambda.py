import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import capture_lambda
from inline_route_store import unpack_route
from ports import RoutePayload

QUEUE_URL = "https://example.invalid/queue-sentinel"
TABLE = "test-table-sentinel"
SECRET_TEXT = "private-details"
KEY = "key-0001-abcdef"

FULL_ENV = {
    "CAPTURE_QUEUE_URL": QUEUE_URL,
    "CAPTURES_TABLE_NAME": TABLE,
}


class FakeDynamo:
    """Remembers what the service writes. It never contacts AWS."""

    def __init__(self):
        self.items = {}
        self.calls = []

    def get_item(self, **kwargs):
        self.calls.append(("get_item", kwargs))
        key = (kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"])
        item = self.items.get(key)
        return {"Item": item} if item is not None else {}

    def put_item(self, **kwargs):
        self.calls.append(("put_item", kwargs))
        item = kwargs["Item"]
        self.items[(item["pk"]["S"], item["sk"]["S"])] = item

    def update_item(self, **kwargs):
        self.calls.append(("update_item", kwargs))


class FakeSqs:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)


class FakeFactory:
    """Stands in for boto3.client and records which clients were requested."""

    def __init__(self):
        self.requested = []
        self.clients = {"dynamodb": FakeDynamo(), "sqs": FakeSqs()}

    def __call__(self, service_name):
        self.requested.append(service_name)
        return self.clients[service_name]


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    capture_lambda.reset_service()
    for name in FULL_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
    capture_lambda.reset_service()


@pytest.fixture
def factory(monkeypatch):
    fake = FakeFactory()
    monkeypatch.setattr(capture_lambda, "_client_factory", fake)
    return fake


def set_env(monkeypatch, **overrides):
    values = {**FULL_ENV, **overrides}
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def health_event():
    return {
        "rawPath": "/api/v1/health",
        "requestContext": {"requestId": "req-1", "http": {"method": "GET"}},
    }


def submit_event(sub="player-1"):
    route = [
        {
            "latitude": 34.7025,
            "longitude": 135.4959,
            "timestamp": f"2026-10-23T01:00:{second:02d}Z",
            "accuracyMeters": 10.0,
        }
        for second in range(4)
    ]
    return {
        "rawPath": "/api/v1/captures",
        "headers": {"idempotency-key": KEY},
        "body": json.dumps({"route": route}),
        "requestContext": {
            "requestId": "req-2",
            "http": {"method": "POST"},
            "authorizer": {"jwt": {"claims": {"sub": sub}}},
        },
    }


def assert_generic_500(response):
    assert response["statusCode"] == 500
    assert response["headers"]["Content-Type"] == "application/json"
    assert response["headers"]["Cache-Control"] == "no-store"
    assert json.loads(response["body"]) == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
    }


# ---------- import ----------


def test_importing_the_module_creates_no_aws_client():
    api_folder = Path(__file__).resolve().parent.parent
    code = (
        "import boto3\n"
        "def fail(*args, **kwargs):\n"
        "    raise AssertionError('an AWS client was created at import time')\n"
        "boto3.client = fail\n"
        "boto3.resource = fail\n"
        "import capture_lambda\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=api_folder,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


# ---------- configuration ----------


@pytest.mark.parametrize("missing", list(FULL_ENV))
def test_missing_variable_returns_generic_500_and_logs_only_the_name(
    monkeypatch, factory, caplog, missing
):
    set_env(monkeypatch, **{missing: None})

    response = capture_lambda.lambda_handler(health_event(), None)

    assert_generic_500(response)
    assert missing in caplog.text
    for value in (QUEUE_URL, TABLE):
        assert value not in caplog.text
        assert value not in response["body"]
    assert factory.requested == []


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_variable_counts_as_missing(monkeypatch, factory, caplog, blank):
    set_env(monkeypatch, CAPTURE_QUEUE_URL=blank)

    response = capture_lambda.lambda_handler(health_event(), None)

    assert_generic_500(response)
    assert "CAPTURE_QUEUE_URL" in caplog.text


def test_all_missing_variables_are_listed(monkeypatch, factory, caplog):
    response = capture_lambda.lambda_handler(health_event(), None)

    assert_generic_500(response)
    for name in FULL_ENV:
        assert name in caplog.text


def test_failed_configuration_is_not_cached(monkeypatch, factory):
    assert capture_lambda.lambda_handler(health_event(), None)["statusCode"] == 500

    set_env(monkeypatch)

    assert capture_lambda.lambda_handler(health_event(), None)["statusCode"] == 200


def test_failure_while_creating_clients_is_generic_and_leaks_nothing(
    monkeypatch, caplog
):
    set_env(monkeypatch)

    def broken_factory(service_name):
        raise RuntimeError(SECRET_TEXT)

    monkeypatch.setattr(capture_lambda, "_client_factory", broken_factory)

    response = capture_lambda.lambda_handler(health_event(), None)

    assert_generic_500(response)
    assert "RuntimeError" in caplog.text
    assert SECRET_TEXT not in caplog.text
    assert SECRET_TEXT not in response["body"]


# ---------- wiring ----------


def test_build_service_requests_the_two_clients(monkeypatch, factory):
    service = capture_lambda.build_service(FULL_ENV, factory)

    assert sorted(factory.requested) == ["dynamodb", "sqs"]
    assert service is not None


def test_service_is_built_once_and_reused(monkeypatch, factory):
    set_env(monkeypatch)

    for _ in range(3):
        assert capture_lambda.lambda_handler(health_event(), None)["statusCode"] == 200

    assert sorted(factory.requested) == ["dynamodb", "sqs"]


def test_health_works_through_lambda_handler(monkeypatch, factory):
    set_env(monkeypatch)

    response = capture_lambda.lambda_handler(health_event(), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "healthy"}


def test_submission_uses_the_configured_resource_names(monkeypatch, factory):
    set_env(monkeypatch)

    response = capture_lambda.lambda_handler(submit_event(sub="real-player"), None)

    body = json.loads(response["body"])
    assert response["statusCode"] == 202
    assert body["status"] == "PENDING"

    dynamo = factory.clients["dynamodb"]
    assert {kwargs["TableName"] for _, kwargs in dynamo.calls} == {TABLE}

    [sqs_call] = factory.clients["sqs"].calls
    assert sqs_call["QueueUrl"] == QUEUE_URL
    message = json.loads(sqs_call["MessageBody"])
    assert message["playerId"] == "real-player"
    assert message["captureId"] == body["captureId"]
    assert message["route"]["encoding"] == "gzip+base64"
    route = unpack_route(RoutePayload(**message["route"]))["route"]
    assert len(route) == 4
    assert route[0]["latitude"] == 34.7025


def test_the_event_is_never_logged(monkeypatch, factory, caplog):
    set_env(monkeypatch)
    caplog.set_level(logging.DEBUG)

    capture_lambda.lambda_handler(submit_event(sub="very-private-subject"), None)

    assert "34.7025" not in caplog.text
    assert "135.4959" not in caplog.text
    assert "very-private-subject" not in caplog.text
