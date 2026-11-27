"""Puts the route inside the queue message: JSON -> gzip -> base64.

This is the technical lead's decision for the MVP (no S3 bucket). The
RouteStore interface is kept, so S3 can be added later without changing the
capture service.

The unpacked route is JSON with exactly the same shape as the request body,
for example {"route": [{"latitude": ..., "longitude": ..., "timestamp": ...,
"accuracyMeters": ...}, ...]}.
"""

import base64
import gzip
import json

from capture_service import format_timestamp
from config import MAX_MESSAGE_BYTES, MESSAGE_ENVELOPE_BYTES
from errors import INVALID_REQUEST, ApiError
from models import GpsSample
from ports import RoutePayload

ENCODING = "gzip+base64"


class InlineRouteStore:
    def __init__(
        self, max_payload_bytes: int = MAX_MESSAGE_BYTES - MESSAGE_ENVELOPE_BYTES
    ) -> None:
        self._max_payload_bytes = max_payload_bytes

    def put(
        self,
        player_id: str,
        capture_id: str,
        samples: list[GpsSample],
    ) -> RoutePayload:
        """Pack the route. The same samples always give the same text, so a retry
        sends the same message. Too large after compression -> 413."""
        document = {
            "route": [
                {
                    "latitude": sample.latitude,
                    "longitude": sample.longitude,
                    "timestamp": format_timestamp(sample.timestamp),
                    "accuracyMeters": sample.accuracy_meters,
                }
                for sample in samples
            ]
        }
        raw = json.dumps(document, separators=(",", ":")).encode("utf-8")
        # mtime=0 keeps the compressed bytes identical for identical input.
        packed = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0))

        if len(packed) > self._max_payload_bytes:
            raise ApiError(
                413, INVALID_REQUEST, "The route is too large to be processed."
            )

        return RoutePayload(encoding=ENCODING, data=packed.decode("ascii"))


def unpack_route(payload: RoutePayload) -> dict:
    """Reverse of put(). The worker does the same; here it is used by the tests."""
    if payload.encoding != ENCODING:
        raise ValueError("Unsupported route encoding.")
    return json.loads(gzip.decompress(base64.b64decode(payload.data, validate=True)))
