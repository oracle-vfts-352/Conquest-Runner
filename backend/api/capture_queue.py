"""The boundary between the API and the SQS queue.

The rest of the API only knows about CaptureJob and the send() method, so it can
be tested without AWS. The message format below is PROPOSED: it is not in
docs/API_CONTRACT.md yet and must be agreed with the worker owner.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError

from config import MAX_MESSAGE_BYTES
from errors import PAYLOAD_TOO_LARGE, ApiError
from models import GpsSample

SCHEMA_VERSION = 1


class QueueUnavailableError(Exception):
    """The job could not be sent to the queue. Nothing was accepted."""


@dataclass(frozen=True)
class CaptureJob:
    """Everything the worker needs to process one capture."""

    capture_id: str
    player_id: str  # always taken from the verified token, never from the body
    request_id: str
    submitted_at: datetime  # timezone-aware, UTC
    samples: list[GpsSample]


class CaptureQueue(Protocol):
    def send(self, job: CaptureJob) -> None:
        """Send the job. Raise QueueUnavailableError if it was not queued."""


def format_timestamp(value: datetime) -> str:
    """Format a UTC datetime like 2026-10-23T01:00:00Z."""
    return value.isoformat().replace("+00:00", "Z")


def serialize_job(job: CaptureJob, max_bytes: int = MAX_MESSAGE_BYTES) -> str:
    """Convert a job to the JSON text sent to SQS."""
    message = {
        "schemaVersion": SCHEMA_VERSION,
        "captureId": job.capture_id,
        "playerId": job.player_id,
        "requestId": job.request_id,
        "submittedAt": format_timestamp(job.submitted_at),
        "route": [
            {
                "latitude": sample.latitude,
                "longitude": sample.longitude,
                "timestamp": format_timestamp(sample.timestamp),
                "accuracyMeters": sample.accuracy_meters,
            }
            for sample in job.samples
        ],
    }
    body = json.dumps(message, separators=(",", ":"))

    if len(body.encode("utf-8")) > max_bytes:
        raise ApiError(
            413,
            PAYLOAD_TOO_LARGE,
            "The route is too large to be processed.",
        )

    return body


class SqsCaptureQueue:
    """Sends capture jobs to an Amazon SQS queue.

    The boto3 SQS client is passed in, so tests can use a fake client.
    """

    def __init__(self, client: object, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    def send(self, job: CaptureJob) -> None:
        body = serialize_job(job)
        try:
            self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)
        except (BotoCoreError, ClientError) as error:
            # Do not put the message or the error details in the text:
            # they could contain GPS data.
            raise QueueUnavailableError("The queue is unavailable.") from error
