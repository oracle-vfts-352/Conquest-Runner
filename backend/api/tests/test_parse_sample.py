import pytest

from errors import INVALID_ROUTE, ApiError
from request_validation import parse_sample


def make_sample(**overrides):
    sample = {
        "latitude": 34.7025,
        "longitude": 135.4959,
        "timestamp": "2026-10-23T01:00:00Z",
        "accuracyMeters": 12.5,
    }
    sample.update(overrides)
    return sample


def assert_invalid_route(raw, expected_text):
    with pytest.raises(ApiError) as exc_info:
        parse_sample(raw, 2)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == INVALID_ROUTE
    assert expected_text in exc_info.value.message


def test_valid_sample_is_parsed():
    sample = parse_sample(make_sample(), 0)

    assert sample.latitude == 34.7025
    assert sample.longitude == 135.4959
    assert sample.accuracy_meters == 12.5
    assert sample.timestamp.isoformat() == "2026-10-23T01:00:00+00:00"


@pytest.mark.parametrize("latitude", [90, -90, 0])
def test_latitude_at_the_limits_is_accepted(latitude):
    assert parse_sample(make_sample(latitude=latitude), 0).latitude == latitude


@pytest.mark.parametrize("longitude", [180, -180, 0])
def test_longitude_at_the_limits_is_accepted(longitude):
    assert parse_sample(make_sample(longitude=longitude), 0).longitude == longitude


def test_accuracy_of_zero_is_accepted():
    assert parse_sample(make_sample(accuracyMeters=0), 0).accuracy_meters == 0


@pytest.mark.parametrize(
    "latitude", [90.1, -90.1, "34.7", None, True, float("nan"), float("inf")]
)
def test_bad_latitude_is_rejected(latitude):
    assert_invalid_route(make_sample(latitude=latitude), "route[2].latitude")


@pytest.mark.parametrize(
    "longitude", [180.1, -180.1, "135.4", None, False, float("nan"), float("-inf")]
)
def test_bad_longitude_is_rejected(longitude):
    assert_invalid_route(make_sample(longitude=longitude), "route[2].longitude")


@pytest.mark.parametrize("accuracy", [-1, "12", None, True, float("nan")])
def test_bad_accuracy_is_rejected(accuracy):
    assert_invalid_route(
        make_sample(accuracyMeters=accuracy), "route[2].accuracyMeters"
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-23 01:00:00",
        "2026-10-23T01:00:00",
        "2026-10-23T10:00:00+09:00",
        "not a time",
        "",
        1729645200,
        None,
    ],
)
def test_bad_timestamp_is_rejected(timestamp):
    assert_invalid_route(make_sample(timestamp=timestamp), "route[2].timestamp")


@pytest.mark.parametrize(
    "missing", ["latitude", "longitude", "timestamp", "accuracyMeters"]
)
def test_missing_field_is_rejected(missing):
    sample = make_sample()
    del sample[missing]

    assert_invalid_route(sample, f"route[2].{missing} is required")


def test_unknown_field_is_rejected():
    assert_invalid_route(make_sample(playerId="someone-else"), "playerId")


@pytest.mark.parametrize("raw", [None, "text", 5, [1, 2], True])
def test_sample_that_is_not_an_object_is_rejected(raw):
    assert_invalid_route(raw, "route[2] must be an object")
