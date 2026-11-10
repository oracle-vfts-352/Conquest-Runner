"""Connects the capture API pieces for AWS Lambda.

handler.py is owned by the technical lead and is NOT changed here. When the
handler is integrated, it can call lambda_handler() from this module.

Rules for this file:
- Importing it never contacts AWS and needs no credentials or region.
- AWS clients are created on the first request and then reused (warm starts).
- The incoming event is never logged: it holds the player's claims and the route.
- The variable names below are PROPOSED and not yet agreed with the technical lead.
"""

import json
import logging
import os
import traceback
from collections.abc import Callable, Mapping

import boto3

from capture_service import CaptureService
from dynamodb_repository import DynamoDbCaptureRepository
from errors import INTERNAL_ERROR, ApiError
from http_api import handle_request
from inline_route_store import InlineRouteStore
from sqs_queue import SqsCaptureQueue

logger = logging.getLogger(__name__)

QUEUE_URL_ENV = "CAPTURE_QUEUE_URL"
TABLE_NAME_ENV = "CAPTURES_TABLE_NAME"
REQUIRED_ENV = (QUEUE_URL_ENV, TABLE_NAME_ENV)

# The service is built once and reused. A failed attempt is never stored.
_cache: dict[str, CaptureService] = {}


class ConfigurationError(Exception):
    """A required environment variable is missing. Only the NAMES are kept."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__("Missing environment variables: " + ", ".join(missing))
        self.missing = missing


def _client_factory(service_name: str) -> object:
    return boto3.client(service_name)


def build_service(
    environ: Mapping[str, str], client_factory: Callable[[str], object]
) -> CaptureService:
    """Create the capture service from environment variables and AWS clients."""
    missing = [name for name in REQUIRED_ENV if not environ.get(name, "").strip()]
    if missing:
        raise ConfigurationError(missing)

    return CaptureService(
        DynamoDbCaptureRepository(client_factory("dynamodb"), environ[TABLE_NAME_ENV]),
        InlineRouteStore(),
        SqsCaptureQueue(client_factory("sqs"), environ[QUEUE_URL_ENV]),
    )


def reset_service() -> None:
    """Forget the cached service. Used by tests."""
    _cache.clear()


def _get_service() -> CaptureService:
    service = _cache.get("service")
    if service is None:
        service = build_service(os.environ, _client_factory)
        _cache["service"] = service
    return service


def _server_error_response() -> dict:
    body = ApiError(500, INTERNAL_ERROR, "An unexpected error occurred.").to_body()
    return {
        "statusCode": 500,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body, separators=(",", ":")),
    }


def lambda_handler(event: dict, context: object) -> dict:
    try:
        service = _get_service()
    except ConfigurationError as error:
        # Names only, never values.
        logger.error("Missing configuration: %s", ", ".join(error.missing))
        return _server_error_response()
    except Exception as error:  # noqa: BLE001 - last safety net, nothing may leak
        logger.error(
            "Could not create the service: %s\n%s",
            type(error).__name__,
            "".join(traceback.format_tb(error.__traceback__)),
        )
        return _server_error_response()

    return handle_request(event, service)
