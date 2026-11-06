import pytest

from errors import (
    INVALID_REQUEST,
    INVALID_ROUTE,
    PAYLOAD_TOO_LARGE,
    ApiError,
)
from request_validation import parse_capture_body


def make_sample(second, **overrides):
    sample = {
        "latitude": 34.7025,
        "longitude": 135.4959,
        "timestamp": f"2026-10-23T01:00:{second:02d}Z",
        "accuracyMeters": 10.0,
    }
    sample.update(overrides)
    return sample


def make_body(count=4):
    return {"route": [make_sample(second) for second in range(count)]}


def assert_error(body, status_code, code, expected_text, **limits):
    with pytest.raises(ApiError) as exc_info:
        parse_capture_body(body, **limits)

    assert exc_info.value.status_code == status_code
    assert exc_info.value.code == code
    assert expected_text in exc_info.value.message


def test_valid_body_returns_samples_in_order():
    samples = parse_capture_body(make_body(5))

    assert len(samples) == 5
    assert samples[0].timestamp < samples[4].timestamp


def test_route_at_the_minimum_size_is_accepted():
    assert len(parse_capture_body(make_body(4))) == 4


def test_route_at_the_maximum_size_is_accepted():
    assert len(parse_capture_body(make_body(6), max_samples=6)) == 6


@pytest.mark.parametrize("body", [None, "text", 5, [1, 2], True])
def test_body_that_is_not_an_object_is_rejected(body):
    assert_error(body, 400, INVALID_REQUEST, "JSON object")


def test_missing_route_is_rejected():
    assert_error({}, 400, INVALID_REQUEST, "route is required")


@pytest.mark.parametrize("route", [None, "text", 5, {"a": 1}])
def test_route_that_is_not_an_array_is_rejected(route):
    assert_error({"route": route}, 400, INVALID_REQUEST, "route must be an array")


@pytest.mark.parametrize("field", ["playerId", "score", "areaM2", "ownership"])
def test_client_supplied_identity_or_result_fields_are_rejected(field):
    body = make_body()
    body[field] = "anything"

    assert_error(body, 400, INVALID_REQUEST, field)


def test_too_few_samples_is_rejected():
    assert_error(make_body(3), 400, INVALID_ROUTE, "at least 4 samples")


def test_empty_route_is_rejected():
    assert_error({"route": []}, 400, INVALID_ROUTE, "at least 4 samples")


def test_too_many_samples_returns_413():
    assert_error(make_body(7), 413, PAYLOAD_TOO_LARGE, "more than 6", max_samples=6)


def test_too_many_samples_is_rejected_before_checking_each_sample():
    body = {"route": ["not a sample"] * 7}

    assert_error(body, 413, PAYLOAD_TOO_LARGE, "more than 6", max_samples=6)


def test_bad_sample_reports_its_position():
    body = make_body()
    body["route"][2]["latitude"] = 200

    assert_error(body, 400, INVALID_ROUTE, "route[2].latitude")


def test_timestamps_that_go_backwards_are_rejected():
    body = make_body()
    body["route"][3]["timestamp"] = "2026-10-23T01:00:01Z"

    assert_error(body, 400, INVALID_ROUTE, "route[3].timestamp must be later")


def test_repeated_timestamp_is_rejected():
    body = make_body()
    body["route"][2]["timestamp"] = body["route"][1]["timestamp"]

    assert_error(body, 400, INVALID_ROUTE, "route[2].timestamp must be later")
