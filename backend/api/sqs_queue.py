"""Sends capture jobs to Amazon SQS.

The message holds the player and capture IDs and the route, compressed
(gzip + base64). The message format is PROPOSED in docs/API_CONTRACT_CHANGES.md.

The SQS client is passed in, so tests can use a fake client without AWS.
"""

import json

from botocore.exceptions import BotoCoreError, ClientError

from config import MAX_MESSAGE_BYTES
from errors import INVALID_REQUEST, ApiError
from ports import CaptureMessage, QueueUnavailableError


def serialize_message(
    message: CaptureMessage, max_bytes: int = MAX_MESSAGE_BYTES
) -> str:
    """Convert the message to JSON text. A hard size check runs AFTER compression."""
    body = json.dumps(
        {
            "schemaVersion": message.schema_version,
            "captureId": message.capture_id,
            "playerId": message.player_id,
            "route": {
                "encoding": message.route.encoding,
                "data": message.route.data,
            },
        },
        separators=(",", ":"),
    )
    if len(body.encode("utf-8")) > max_bytes:
        raise ApiError(413, INVALID_REQUEST, "The route is too large to be processed.")
    return body


class SqsCaptureQueue:
    def __init__(self, client: object, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    def send(self, message: CaptureMessage) -> None:
        body = serialize_message(message)
        try:
            self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)
        except (BotoCoreError, ClientError) as error:
            raise QueueUnavailableError("The queue is unavailable.") from error
