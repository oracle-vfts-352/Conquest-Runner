"""Interfaces (ports) that the capture service depends on.

The real implementations (DynamoDB, S3, SQS) are written later. Tests use the
in-memory fakes in tests/fakes.py, so no AWS account is needed.

The message format and the S3 claim-check design follow the PROPOSAL in
docs/API_CONTRACT.md section 4.3. It is not a final team decision yet.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from models import GpsSample

# Capture statuses (docs/API_CONTRACT.md section 5.2).
# RECEIVED is internal only: the request is stored but not yet queued.
# It is never shown to clients.
RECEIVED = "RECEIVED"
PENDING = "PENDING"
PROCESSING = "PROCESSING"
SUCCEEDED = "SUCCEEDED"
REJECTED = "REJECTED"
FAILED = "FAILED"

SCHEMA_VERSION = 1


class StorageUnavailableError(Exception):
    """The database or the route store could not be used."""


class QueueUnavailableError(Exception):
    """The job could not be sent to the queue. Nothing was accepted."""


@dataclass(frozen=True)
class RouteObject:
    """Where the full route is stored (the 'claim check')."""

    bucket: str
    key: str


@dataclass(frozen=True)
class CaptureRecord:
    capture_id: str
    player_id: str
    request_hash: str  # SHA-256 of the route, used to detect key reuse
    status: str
    created_at: datetime  # timezone-aware, UTC
    updated_at: datetime
    result: dict | None = None  # filled in by the worker
    error: dict | None = None  # filled in by the worker


@dataclass(frozen=True)
class CaptureMessage:
    """The small message sent to the worker. It holds no GPS data."""

    capture_id: str
    player_id: str  # always from the verified token, never from the request body
    route_object: RouteObject
    schema_version: int = SCHEMA_VERSION


class CaptureRepository(Protocol):
    def get(self, player_id: str, capture_id: str) -> CaptureRecord | None:
        """Return the player's capture, or None. Raise StorageUnavailableError on failure."""

    def create(self, record: CaptureRecord) -> bool:
        """Store a new record. Return False if it already exists (nothing is changed)."""

    def mark_pending(self, player_id: str, capture_id: str, now: datetime) -> None:
        """Change RECEIVED to PENDING. Do nothing if the status is already different.

        The worker may already have moved the capture on, and its progress must
        never be overwritten.
        """


class RouteStore(Protocol):
    def put(
        self, player_id: str, capture_id: str, samples: list[GpsSample]
    ) -> RouteObject:
        """Store the route. The same input must always give the same RouteObject
        (saving again just overwrites), so a retry is safe."""


class CaptureQueue(Protocol):
    def send(self, message: CaptureMessage) -> None:
        """Send the message. Raise QueueUnavailableError if it was not queued."""
