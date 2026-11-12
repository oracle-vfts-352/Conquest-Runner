"""API error codes and the exception used to report them.

Codes under "In the contract" appear in docs/API_CONTRACT.md (sections 4.5 and 6.2).
Codes under "Proposed" are NOT in the contract yet and need team agreement.
"""

# --- In the contract ---
INVALID_REQUEST = "INVALID_REQUEST"
INVALID_ROUTE = "INVALID_ROUTE"  # geometry problems: reported later by the worker
IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
RATE_LIMITED = "RATE_LIMITED"
INTERNAL_ERROR = "INTERNAL_ERROR"
UNAUTHORIZED = "UNAUTHORIZED"  # in the 401 example, but missing from the table in 6.2

# --- Proposed (unfinished: not in the contract yet) ---
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
