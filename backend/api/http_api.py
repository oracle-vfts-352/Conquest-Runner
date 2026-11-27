"""The HTTP layer: turns an API Gateway HTTP API event into a response.

It reads the request, checks who is calling, and calls the CaptureService.
It does not contain game or storage logic.

Event format: API Gateway HTTP API payload version 2.0.
"""

import base64
import binascii
import json
import logging
import re
import traceback

from capture_service import CaptureService
from config import MAX_BODY_BYTES
from errors import INTERNAL_ERROR, INVALID_REQUEST, UNAUTHORIZED, ApiError
from request_validation import parse_capture_body

logger = logging.getLogger(__name__)

# PROPOSED: not in docs/API_CONTRACT.md. Only used for a path we do not handle.
NOT_FOUND = "NOT_FOUND"

CAPTURES_PATH = "/api/v1/captures"
HEALTH_PATH = "/api/v1/health"
CAPTURE_ID_PATTERN = re.compile(r"/api/v1/captures/([A-Za-z0-9_-]{1,100})")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}")


def _dig(value: object, *names: str) -> object:
    """Read value[name1][name2]... and return None if any step is missing."""
    for name in names:
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",  # responses are private to the player
        },
        "body": json.dumps(body, separators=(",", ":")),
    }


def _player_id(event: dict) -> str:
    """The caller's identity. It comes ONLY from the claims that API Gateway
    verified, never from the request body or any header."""
    subject = _dig(event, "requestContext", "authorizer", "jwt", "claims", "sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ApiError(401, UNAUTHORIZED, "Authentication is required.")
    return subject


def _idempotency_key(event: dict) -> str:
    headers = event.get("headers")
    value = None
    if isinstance(headers, dict):
        for name, header_value in headers.items():
            if isinstance(name, str) and name.lower() == "idempotency-key":
                value = header_value
                break
    if value is None:
        raise ApiError(400, INVALID_REQUEST, "The Idempotency-Key header is required.")
    if not isinstance(value, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise ApiError(
            400,
            INVALID_REQUEST,
            "The Idempotency-Key header must be 8 to 128 characters: "
            "letters, digits, '-' or '_'.",
        )
    return value


def _read_json_body(event: dict, max_body_bytes: int) -> object:
    raw = event.get("body")
    if not isinstance(raw, str) or raw == "":
        raise ApiError(400, INVALID_REQUEST, "The request body is invalid.")

    if event.get("isBase64Encoded") is True:
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ApiError(
                400, INVALID_REQUEST, "The request body is invalid."
            ) from error
    else:
        data = raw.encode("utf-8")

    if len(data) > max_body_bytes:
        raise ApiError(
            413, INVALID_REQUEST, "The request body exceeds the configured size limit."
        )

    try:
        return json.loads(data)
    except (ValueError, RecursionError) as error:
        raise ApiError(400, INVALID_REQUEST, "The request body is invalid.") from error


def _submit_capture(
    event: dict, service: CaptureService, max_body_bytes: int
) -> tuple[int, dict]:
    player_id = _player_id(event)
    idempotency_key = _idempotency_key(event)
    samples = parse_capture_body(_read_json_body(event, max_body_bytes))

    result = service.submit(player_id, idempotency_key, samples)

    # 202: accepted just now. 200: this request was already accepted (a retry).
    status_code = 200 if result.already_accepted else 202
    return status_code, {
        "captureId": result.capture_id,
        "status": result.status,
        "statusUrl": f"{CAPTURES_PATH}/{result.capture_id}",
    }


def _route(
    event: dict, service: CaptureService, max_body_bytes: int
) -> tuple[int, dict]:
    method = _dig(event, "requestContext", "http", "method")
    path = event.get("rawPath")
    method = method.upper() if isinstance(method, str) else ""

    if not isinstance(path, str):
        raise ApiError(404, NOT_FOUND, "The requested resource was not found.")

    if method == "GET" and path == HEALTH_PATH:
        return 200, {"status": "healthy"}

    if method == "POST" and path == CAPTURES_PATH:
        return _submit_capture(event, service, max_body_bytes)

    match = CAPTURE_ID_PATTERN.fullmatch(path)
    if method == "GET" and match:
        return 200, service.get_status(_player_id(event), match.group(1))

    raise ApiError(404, NOT_FOUND, "The requested resource was not found.")


def handle_request(
    event: dict, service: CaptureService, max_body_bytes: int = MAX_BODY_BYTES
) -> dict:
    """Handle one API Gateway event and return an API Gateway response."""
    request_id = _dig(event, "requestContext", "requestId")

    try:
        status_code, body = _route(event, service, max_body_bytes)
    except ApiError as error:
        status_code, body = error.status_code, error.to_body()
    except Exception as error:  # noqa: BLE001 - the last safety net: never leak details
        # Log where it failed, but NOT the exception message: it could contain
        # private GPS data. The client only gets a generic message.
        logger.error(
            "Unhandled %s (requestId=%s)\n%s",
            type(error).__name__,
            request_id,
            "".join(traceback.format_tb(error.__traceback__)),
        )
        status_code = 500
        body = ApiError(500, INTERNAL_ERROR, "An unexpected error occurred.").to_body()

    # Only the status and request ID are logged, never the body or any GPS data.
    logger.info("Handled request status=%s requestId=%s", status_code, request_id)
    return _response(status_code, body)
