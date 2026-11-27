import json
import random
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeCaptureRepository

from capture_service import CaptureService
from config import MAX_MESSAGE_BYTES, MAX_SAMPLES
from errors import INVALID_REQUEST, ApiError
from inline_route_store import ENCODING, InlineRouteStore, unpack_route
from models import GpsSample
from ports import RoutePayload
from sqs_queue import SqsCaptureQueue, serialize_message

START = datetime(2026, 10, 23, 1, 0, 0, tzinfo=UTC)
PLAYER = "11111111-2222-3333-4444-555555555555"
CAPTURE = "capture_0123456789abcdef0123456789abcdef"


def walking_route(count):
    """A realistic route: small steps, one point per second."""
    generator = random.Random(1)
    latitude, longitude = 34.7025, 135.4959
    samples = []
    for index in range(count):
        latitude += generator.uniform(-2e-5, 2e-5)
        longitude += generator.uniform(-2e-5, 2e-5)
        samples.append(
            GpsSample(
                round(latitude, 7),
                round(longitude, 7),
                START + timedelta(seconds=index),
                round(generator.uniform(3, 20), 1),
            )
        )
    return samples


def worst_case_route(count):
    """Points that do not compress well: random places, irregular times."""
    generator = random.Random(7)
    samples = []
    moment = START
    for _ in range(count):
        moment += timedelta(
            seconds=generator.randint(1, 59), milliseconds=generator.randint(1, 999)
        )
        samples.append(
            GpsSample(
                round(generator.uniform(-90, 90), 7),
                round(generator.uniform(-180, 180), 7),
                moment,
                round(generator.uniform(0, 500), 2),
            )
        )
    return samples


class FakeSqsClient:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {}


def test_route_is_packed_as_gzip_and_base64():
    payload = InlineRouteStore().put(PLAYER, CAPTURE, walking_route(4))

    assert payload.encoding == ENCODING == "gzip+base64"
    assert payload.data.isascii()
    assert payload.data.startswith("H4sI")  # base64 of the gzip header


def test_unpacked_route_has_the_same_shape_as_the_request_body():
    samples = walking_route(4)

    unpacked = unpack_route(InlineRouteStore().put(PLAYER, CAPTURE, samples))

    assert set(unpacked) == {"route"}
    assert len(unpacked["route"]) == 4
    assert unpacked["route"][1] == {
        "latitude": samples[1].latitude,
        "longitude": samples[1].longitude,
        "timestamp": "2026-10-23T01:00:01Z",
        "accuracyMeters": samples[1].accuracy_meters,
    }


def test_same_route_always_gives_the_same_payload():
    store = InlineRouteStore()

    first = store.put(PLAYER, CAPTURE, walking_route(50))
    second = store.put(PLAYER, CAPTURE, walking_route(50))

    assert first == second


def test_payload_too_large_after_compression_is_rejected_with_413():
    store = InlineRouteStore(max_payload_bytes=100)

    with pytest.raises(ApiError) as exc_info:
        store.put(PLAYER, CAPTURE, worst_case_route(200))

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == INVALID_REQUEST


def test_unknown_encoding_cannot_be_unpacked():
    with pytest.raises(ValueError):
        unpack_route(RoutePayload(encoding="zip", data="abc"))


def test_a_realistic_maximum_size_route_fits_even_in_an_old_256_kib_queue():
    store = InlineRouteStore()

    payload = store.put(PLAYER, CAPTURE, walking_route(MAX_SAMPLES))

    assert len(payload.data) < 262_144


def test_the_worst_case_maximum_size_route_fits_in_one_sqs_message():
    # 10,000 random points: the largest message the API can ever produce.
    sqs_client = FakeSqsClient()
    service = CaptureService(
        FakeCaptureRepository(),
        InlineRouteStore(),
        SqsCaptureQueue(sqs_client, "https://example.invalid/queue"),
    )
    samples = worst_case_route(MAX_SAMPLES)

    service.submit(PLAYER, "key-0001-abcdef", samples)

    body = sqs_client.calls[0]["MessageBody"]
    assert len(body.encode("utf-8")) < MAX_MESSAGE_BYTES
    message = json.loads(body)
    unpacked = unpack_route(RoutePayload(**message["route"]))
    assert len(unpacked["route"]) == MAX_SAMPLES
    assert unpacked["route"][-1]["latitude"] == samples[-1].latitude


def test_message_size_check_uses_the_final_message_not_just_the_route():
    payload = InlineRouteStore().put(PLAYER, CAPTURE, walking_route(100))
    from ports import CaptureMessage

    message = CaptureMessage(CAPTURE, PLAYER, payload)
    size = len(serialize_message(message).encode("utf-8"))

    assert size > len(payload.data)
    with pytest.raises(ApiError):
        serialize_message(message, max_bytes=len(payload.data))
