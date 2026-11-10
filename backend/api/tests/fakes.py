"""In-memory stand-ins for DynamoDB, S3 and SQS.

These are test fakes only. They are NOT real server data and never contact AWS.
Setting `fail = True` makes a fake behave as if the service were down.
"""

from dataclasses import replace
from datetime import datetime

from models import GpsSample
from ports import (
    PENDING,
    RECEIVED,
    CaptureMessage,
    CaptureRecord,
    QueueUnavailableError,
    RoutePayload,
    StorageUnavailableError,
)


class FakeCaptureRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], CaptureRecord] = {}
        self.fail_get = False
        self.fail_create = False
        self.fail_mark_pending = False

    def get(self, player_id: str, capture_id: str) -> CaptureRecord | None:
        if self.fail_get:
            raise StorageUnavailableError("fake get failure")
        return self.records.get((player_id, capture_id))

    def create(self, record: CaptureRecord) -> bool:
        if self.fail_create:
            raise StorageUnavailableError("fake create failure")
        key = (record.player_id, record.capture_id)
        if key in self.records:
            return False
        self.records[key] = record
        return True

    def mark_pending(self, player_id: str, capture_id: str, now: datetime) -> None:
        if self.fail_mark_pending:
            raise StorageUnavailableError("fake mark_pending failure")
        key = (player_id, capture_id)
        record = self.records[key]
        if record.status == RECEIVED:
            self.records[key] = replace(record, status=PENDING, updated_at=now)

    def set_record(self, record: CaptureRecord) -> None:
        """Test helper: put a record in directly (for example, one set by the worker)."""
        self.records[(record.player_id, record.capture_id)] = record


class FakeRouteStore:
    def __init__(self) -> None:
        self.stored: dict[str, list[GpsSample]] = {}
        self.put_count = 0
        self.fail = False

    def put(
        self, player_id: str, capture_id: str, samples: list[GpsSample]
    ) -> RoutePayload:
        if self.fail:
            raise StorageUnavailableError("fake route store failure")
        self.put_count += 1
        reference = f"{player_id}/{capture_id}"
        self.stored[reference] = samples
        return RoutePayload(encoding="fake", data=reference)


class FakeCaptureQueue:
    def __init__(self) -> None:
        self.messages: list[CaptureMessage] = []
        self.fail = False

    def send(self, message: CaptureMessage) -> None:
        if self.fail:
            raise QueueUnavailableError("fake queue failure")
        self.messages.append(message)
