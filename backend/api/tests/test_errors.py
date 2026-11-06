from errors import INVALID_REQUEST, ApiError


def test_api_error_keeps_status_code_and_code():
    error = ApiError(400, INVALID_REQUEST, "The request body is invalid.")

    assert error.status_code == 400
    assert error.code == "INVALID_REQUEST"


def test_api_error_body_matches_contract_shape():
    error = ApiError(400, INVALID_REQUEST, "The request body is invalid.")

    assert error.to_body() == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "The request body is invalid.",
        }
    }
