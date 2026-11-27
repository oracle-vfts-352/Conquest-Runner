"""Health (alive) and ready (configuration) checks of the Lambda entry point.

No AWS is contacted. The AWS client factory is replaced by a fake.
"""

import json

import pytest

import capture_lambda
from capture_lambda import (
    QUEUE_URL_ENV,
    READY_PATH,
    TABLE_NAME_ENV,
    lambda_handler,
    reset_service,
)
from http_api import HEALTH_PATH


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    reset_service()
    monkeypatch.delenv(QUEUE_URL_ENV, raising=False)
    monkeypatch.delenv(TABLE_NAME_ENV, raising=False)
    yield
    reset_service()


@pytest.fixture
def factory_calls(monkeypatch):
    calls: list[str] = []

    def fake_factory(service_name: str) -> object:
        calls.append(service_name)
        return object()

    monkeypatch.setattr(capture_lambda, "_client_factory", fake_factory)
    return calls


def set_config(monkeypatch):
    monkeypatch.setenv(QUEUE_URL_ENV, "https://sqs.example.invalid/fake-queue")
    monkeypatch.setenv(TABLE_NAME_ENV, "fake-table")


def event(method, path):
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"requestId": "test-1", "http": {"method": method}},
    }


def test_health_is_200_without_any_configuration(factory_calls):
    response = lambda_handler(event("GET", HEALTH_PATH), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "healthy"}
    assert response["headers"]["Cache-Control"] == "no-store"
    assert response["headers"]["Content-Type"] == "application/json"


def test_health_never_builds_the_service(factory_calls):
    lambda_handler(event("GET", HEALTH_PATH), None)

    assert factory_calls == []
    assert capture_lambda._cache == {}


def test_health_needs_no_login(factory_calls):
    # The event has no authorizer claims at all.
    response = lambda_handler(event("GET", HEALTH_PATH), None)

    assert response["statusCode"] == 200


def test_health_only_answers_get(factory_calls):
    response = lambda_handler(event("POST", HEALTH_PATH), None)

    # Falls through to the normal path, where the missing configuration fails.
    assert response["statusCode"] == 500


@pytest.mark.parametrize("bad_event", [None, "text", [], {}, {"requestContext": 5}])
def test_odd_events_do_not_crash_the_health_check(bad_event, factory_calls):
    response = lambda_handler(bad_event, None)

    assert response["statusCode"] in (400, 404, 500)


def test_ready_is_503_when_configuration_is_missing(factory_calls):
    response = lambda_handler(event("GET", READY_PATH), None)

    body = json.loads(response["body"])
    assert response["statusCode"] == 503
    assert body["error"]["code"] == "INTERNAL_ERROR"


def test_ready_response_does_not_name_the_missing_variables(factory_calls):
    response = lambda_handler(event("GET", READY_PATH), None)

    assert QUEUE_URL_ENV not in response["body"]
    assert TABLE_NAME_ENV not in response["body"]


def test_ready_is_200_when_configuration_is_complete(monkeypatch, factory_calls):
    set_config(monkeypatch)

    response = lambda_handler(event("GET", READY_PATH), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ready"}


def test_ready_recovers_after_the_configuration_is_fixed(monkeypatch, factory_calls):
    assert lambda_handler(event("GET", READY_PATH), None)["statusCode"] == 503

    set_config(monkeypatch)

    assert lambda_handler(event("GET", READY_PATH), None)["statusCode"] == 200


def test_ready_reuses_the_service_on_the_next_call(monkeypatch, factory_calls):
    set_config(monkeypatch)

    lambda_handler(event("GET", READY_PATH), None)
    lambda_handler(event("GET", READY_PATH), None)

    assert factory_calls == ["dynamodb", "sqs"]


def test_ready_is_503_when_an_aws_client_cannot_be_created(monkeypatch):
    set_config(monkeypatch)

    def broken_factory(service_name: str) -> object:
        raise RuntimeError("secret-detail-that-must-not-leak")

    monkeypatch.setattr(capture_lambda, "_client_factory", broken_factory)

    response = lambda_handler(event("GET", READY_PATH), None)

    assert response["statusCode"] == 503
    assert "secret-detail" not in response["body"]


def test_other_routes_still_fail_with_500_when_configuration_is_missing(
    factory_calls,
):
    response = lambda_handler(event("GET", "/api/v1/captures/capture_abc"), None)

    assert response["statusCode"] == 500
