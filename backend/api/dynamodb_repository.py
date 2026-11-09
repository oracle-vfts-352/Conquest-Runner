"""Stores capture records in Amazon DynamoDB.

THE TABLE DESIGN BELOW IS A PROPOSAL. docs/DATA_MODEL.md is empty and the
technical lead has not approved it. If it changes, only this file changes.

One item per capture:

    pk          "PLAYER#<playerId>"          (partition key)
    sk          "CAPTURE#<captureId>"        (sort key)
    captureId, playerId, requestHash         strings
    status      RECEIVED | PENDING | PROCESSING | SUCCEEDED | REJECTED | FAILED
    createdAt, updatedAt                     ISO 8601 UTC strings, e.g. 2026-10-23T01:00:00Z
    result      map   (written by the worker when SUCCEEDED)
    error       map   (written by the worker when REJECTED or FAILED)

The record never contains GPS data; the route lives in the route store.
Because the player ID is part of the key, a player can only ever read items
under their own partition. Retention (a TTL attribute) is not decided yet.

The DynamoDB client is passed in, so tests can use a fake without AWS.
"""

from datetime import datetime
from decimal import Decimal

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import BotoCoreError, ClientError

from capture_service import format_timestamp
from ports import PENDING, RECEIVED, CaptureRecord, StorageUnavailableError

_CONDITION_FAILED = "ConditionalCheckFailedException"
_deserializer = TypeDeserializer()


def _key(player_id: str, capture_id: str) -> dict:
    return {
        "pk": {"S": f"PLAYER#{player_id}"},
        "sk": {"S": f"CAPTURE#{capture_id}"},
    }


def _is_condition_failure(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == _CONDITION_FAILED


def _plain(value: object) -> object:
    """Turn DynamoDB numbers (Decimal) into int or float so they can be sent as JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {name: _plain(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _text(item: dict, name: str) -> str:
    value = item[name]
    if not isinstance(value, str):
        raise TypeError(f"{name} is not a string")
    return value


def _time(item: dict, name: str) -> datetime:
    parsed = datetime.fromisoformat(_text(item, name))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} has no time zone")
    return parsed


def _record_from_item(raw_item: dict) -> CaptureRecord:
    try:
        item = {name: _deserializer.deserialize(v) for name, v in raw_item.items()}
        result = _plain(item.get("result"))
        error = _plain(item.get("error"))
        if result is not None and not isinstance(result, dict):
            raise TypeError("result is not a map")
        if error is not None and not isinstance(error, dict):
            raise TypeError("error is not a map")
        return CaptureRecord(
            capture_id=_text(item, "captureId"),
            player_id=_text(item, "playerId"),
            request_hash=_text(item, "requestHash"),
            status=_text(item, "status"),
            created_at=_time(item, "createdAt"),
            updated_at=_time(item, "updatedAt"),
            result=result,
            error=error,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise StorageUnavailableError(
            "The stored capture could not be read."
        ) from error


class DynamoDbCaptureRepository:
    def __init__(self, client: object, table_name: str) -> None:
        self._client = client
        self._table_name = table_name

    def get(self, player_id: str, capture_id: str) -> CaptureRecord | None:
        try:
            # A consistent read, so a retry always sees the record it just created.
            response = self._client.get_item(
                TableName=self._table_name,
                Key=_key(player_id, capture_id),
                ConsistentRead=True,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageUnavailableError("The database is unavailable.") from error

        item = response.get("Item")
        return None if item is None else _record_from_item(item)

    def create(self, record: CaptureRecord) -> bool:
        item = {
            **_key(record.player_id, record.capture_id),
            "captureId": {"S": record.capture_id},
            "playerId": {"S": record.player_id},
            "requestHash": {"S": record.request_hash},
            "status": {"S": record.status},
            "createdAt": {"S": format_timestamp(record.created_at)},
            "updatedAt": {"S": format_timestamp(record.updated_at)},
        }
        try:
            self._client.put_item(
                TableName=self._table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as error:
            if _is_condition_failure(error):
                return False  # it already exists; nothing was changed
            raise StorageUnavailableError("The database is unavailable.") from error
        except BotoCoreError as error:
            raise StorageUnavailableError("The database is unavailable.") from error
        return True

    def mark_pending(self, player_id: str, capture_id: str, now: datetime) -> None:
        try:
            # Only change RECEIVED to PENDING. If the worker already moved the
            # capture on, the condition fails and its progress is kept.
            self._client.update_item(
                TableName=self._table_name,
                Key=_key(player_id, capture_id),
                UpdateExpression="SET #s = :pending, updatedAt = :now",
                ConditionExpression="#s = :received",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":pending": {"S": PENDING},
                    ":received": {"S": RECEIVED},
                    ":now": {"S": format_timestamp(now)},
                },
            )
        except ClientError as error:
            if _is_condition_failure(error):
                return
            raise StorageUnavailableError("The database is unavailable.") from error
        except BotoCoreError as error:
            raise StorageUnavailableError("The database is unavailable.") from error
