"""API error codes and the exception used to report them.

Codes marked "contract" are listed in docs/API_CONTRACT.md section 7.
Codes marked "proposed" are NOT in the contract yet and need team agreement.
"""

# --- In the contract ---
INVALID_REQUEST = "INVALID_REQUEST"
INVALID_ROUTE = "INVALID_ROUTE"
IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
RATE_LIMITED = "RATE_LIMITED"
INTERNAL_ERROR = "INTERNAL_ERROR"

# --- Proposed (unfinished: not in the contract yet) ---
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"  # HTTP 413
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"  # HTTP 503
CAPTURE_NOT_FOUND = "CAPTURE_NOT_FOUND"  # HTTP 404


class ApiError(Exception):
    """An error that should be returned to the client as JSON."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}
