"""Structural validation of capture requests.

This checks the shape and ranges of the data only. Loop closure, distance,
area, and speed rules belong to the worker (see docs/GAME_RULES.md).
"""

import math
from datetime import UTC, datetime

from config import MAX_SAMPLES, MIN_SAMPLES
from errors import INVALID_REQUEST, ApiError
from models import GpsSample

REQUIRED_SAMPLE_FIELDS = ("latitude", "longitude", "timestamp", "accuracyMeters")


def _invalid(message: str) -> ApiError:
    return ApiError(400, INVALID_REQUEST, message)


def _is_finite_number(value: object) -> bool:
    # bool is a subclass of int in Python, so exclude it explicitly.
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _parse_timestamp(value: object) -> datetime | None:
    """Accept only ISO 8601 UTC strings that end with 'Z'."""
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def parse_sample(raw: object, index: int) -> GpsSample:
    """Validate one GPS sample and return it as a GpsSample."""
    where = f"route[{index}]"

    if not isinstance(raw, dict):
        raise _invalid(f"{where} must be an object.")

    for name in REQUIRED_SAMPLE_FIELDS:
        if name not in raw:
            raise _invalid(f"{where}.{name} is required.")

    unknown = sorted(set(raw) - set(REQUIRED_SAMPLE_FIELDS))
    if unknown:
        raise _invalid(f"{where} has unsupported field: {unknown[0]}.")

    latitude = raw["latitude"]
    if not _is_finite_number(latitude) or not -90 <= latitude <= 90:
        raise _invalid(f"{where}.latitude must be a number from -90 to 90.")

    longitude = raw["longitude"]
    if not _is_finite_number(longitude) or not -180 <= longitude <= 180:
        raise _invalid(f"{where}.longitude must be a number from -180 to 180.")

    accuracy = raw["accuracyMeters"]
    if not _is_finite_number(accuracy) or accuracy < 0:
        raise _invalid(f"{where}.accuracyMeters must be a number of 0 or more.")

    timestamp = _parse_timestamp(raw["timestamp"])
    if timestamp is None:
        raise _invalid(f"{where}.timestamp must be an ISO 8601 UTC time ending with Z.")

    return GpsSample(
        latitude=float(latitude),
        longitude=float(longitude),
        timestamp=timestamp,
        accuracy_meters=float(accuracy),
    )


def parse_capture_body(
    body: object,
    min_samples: int = MIN_SAMPLES,
    max_samples: int = MAX_SAMPLES,
) -> list[GpsSample]:
    """Validate the body of POST /api/v1/captures and return its samples.

    The body must be exactly {"route": [...]}. Any other field (for example
    playerId, score, or area) is rejected, because the client is never trusted
    to supply identity or results.
    """
    if not isinstance(body, dict):
        raise ApiError(400, INVALID_REQUEST, "The request body must be a JSON object.")

    unknown = sorted(set(body) - {"route"})
    if unknown:
        raise ApiError(
            400, INVALID_REQUEST, f"The request has an unsupported field: {unknown[0]}."
        )

    if "route" not in body:
        raise ApiError(400, INVALID_REQUEST, "route is required.")

    route = body["route"]
    if not isinstance(route, list):
        raise ApiError(400, INVALID_REQUEST, "route must be an array.")

    if len(route) > max_samples:
        raise ApiError(
            413,
            INVALID_REQUEST,
            f"route must not contain more than {max_samples} samples.",
        )

    if len(route) < min_samples:
        raise _invalid(f"route must contain at least {min_samples} samples.")

    samples = [parse_sample(raw, index) for index, raw in enumerate(route)]

    for index in range(1, len(samples)):
        if samples[index].timestamp <= samples[index - 1].timestamp:
            raise _invalid(
                f"route[{index}].timestamp must be later than route[{index - 1}].timestamp."
            )

    return samples
