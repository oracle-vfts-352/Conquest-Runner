"""Sends capture jobs to Amazon SQS.

The message is small and holds no GPS data: only where the route is stored
(docs/API_CONTRACT.md section 4.3, a PROPOSAL, not final).

The SQS client is passed in, so tests can use a fake client without AWS.
"""

import json

from botocore.exceptions import BotoCoreError, ClientError

from ports import CaptureMessage, QueueUnavailableError


def serialize_message(message: CaptureMessage) -> str:
    return json.dumps(
        {
            "schemaVersion": message.schema_version,
            "captureId": message.capture_id,
            "playerId": message.player_id,
            "routeObject": {
                "bucket": message.route_object.bucket,
                "key": message.route_object.key,
            },
        },
        separators=(",", ":"),
    )


class SqsCaptureQueue:
    def __init__(self, client: object, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    def send(self, message: CaptureMessage) -> None:
        try:
            self._client.send_message(
                QueueUrl=self._queue_url, MessageBody=serialize_message(message)
            )
        except (BotoCoreError, ClientError) as error:
            raise QueueUnavailableError("The queue is unavailable.") from error
