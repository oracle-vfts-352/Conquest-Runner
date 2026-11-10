"""The capture service: the rules for accepting a capture and reporting its status.

It knows nothing about HTTP, DynamoDB, S3 or SQS. It only uses the interfaces
in ports.py, so it can be tested without AWS.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

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
    RECEIVED,
    REJECTED,
    SUCCEEDED,
    CaptureMessage,
    CaptureQueue,
    CaptureRecord,
    CaptureRepository,
    QueueUnavailableError,
    RouteStore,
    StorageUnavailableError,
)


@dataclass(frozen=True)
class SubmitResult:
    capture_id: str
    status: str
    # False: accepted just now. True: this request was accepted earlier (a retry).
    already_accepted: bool


def format_timestamp(value: datetime) -> str:
    """Format a UTC datetime like 2026-10-23T01:00:00Z."""
    return value.isoformat().replace("+00:00", "Z")


def derive_capture_id(player_id: str, idempotency_key: str) -> str:
    """Always give the same ID for the same player and key.

    A retry therefore finds the same capture, and one player's key can never
    collide with another player's key.
    """
    digest = hashlib.sha256(f"{player_id}\n{idempotency_key}".encode()).hexdigest()
    return f"capture_{digest[:32]}"


def hash_samples(samples: list[GpsSample]) -> str:
    """A fingerprint of the route, used to detect a key reused with other content."""
    canonical = json.dumps(
        [
            [s.latitude, s.longitude, format_timestamp(s.timestamp), s.accuracy_meters]
            for s in samples
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _unavailable(message: str) -> ApiError:
    return ApiError(503, INTERNAL_ERROR, message)


class CaptureService:
    def __init__(
        self,
        repository: CaptureRepository,
        route_store: RouteStore,
        queue: CaptureQueue,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._route_store = route_store
        self._queue = queue
        self._clock = clock

    def submit(
        self, player_id: str, idempotency_key: str, samples: list[GpsSample]
    ) -> SubmitResult:
        """Accept a validated route for processing.

        Order: record (RECEIVED) -> prepare route -> send to queue -> PENDING.
        It only reports success after the queue accepted the message. If any
        step fails, the client retries with the same key and the steps are
        simply repeated. Every step is safe to repeat, and the worker must
        ignore duplicate messages for the same captureId.
        """
        capture_id = derive_capture_id(player_id, idempotency_key)
        request_hash = hash_samples(samples)

        try:
            record = self._find_or_create(player_id, capture_id, request_hash)
            if record.status != RECEIVED:
                return SubmitResult(capture_id, record.status, already_accepted=True)

            route_payload = self._route_store.put(player_id, capture_id, samples)
            self._queue.send(CaptureMessage(capture_id, player_id, route_payload))
            self._repository.mark_pending(player_id, capture_id, self._clock())
        except (StorageUnavailableError, QueueUnavailableError) as error:
            raise _unavailable(
                "The capture request could not be accepted at this time."
            ) from error

        return SubmitResult(capture_id, PENDING, already_accepted=False)

    def get_status(self, player_id: str, capture_id: str) -> dict:
        """Return the status of one of the player's own captures."""
        try:
            record = self._repository.get(player_id, capture_id)
        except StorageUnavailableError as error:
            raise _unavailable(
                "The capture status could not be retrieved at this time."
            ) from error

        # Unknown, another player's, and not-yet-accepted captures look the same.
        if record is None or record.status == RECEIVED:
            raise ApiError(404, CAPTURE_NOT_FOUND, "The capture was not found.")

        body = {
            "captureId": record.capture_id,
            "status": record.status,
            "createdAt": format_timestamp(record.created_at),
            "updatedAt": format_timestamp(record.updated_at),
        }
        if record.status == SUCCEEDED and record.result is not None:
            body["result"] = record.result
        if record.status in (REJECTED, FAILED) and record.error is not None:
            body["error"] = record.error
        return body

    def _find_or_create(
        self, player_id: str, capture_id: str, request_hash: str
    ) -> CaptureRecord:
        existing = self._repository.get(player_id, capture_id)

        if existing is None:
            now = self._clock()
            new_record = CaptureRecord(
                capture_id=capture_id,
                player_id=player_id,
                request_hash=request_hash,
                status=RECEIVED,
                created_at=now,
                updated_at=now,
            )
            if self._repository.create(new_record):
                return new_record
            # Another request created it at the same moment: use that one.
            existing = self._repository.get(player_id, capture_id)
            if existing is None:
                raise StorageUnavailableError("The record disappeared.")

        if existing.request_hash != request_hash:
            raise ApiError(
                409,
                IDEMPOTENCY_KEY_CONFLICT,
                "The idempotency key is already associated with a different request.",
            )
        return existing
