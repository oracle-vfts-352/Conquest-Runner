
@'
# ConquestRunner — API Contract

## 1. Purpose

This document defines the initial HTTP API for the ConquestRunner MVP.

The API accepts authenticated capture requests, queues them for asynchronous processing, and exposes capture status. The backend is the source of truth for route validity, ownership, and scores.

This is the proposed contract for implementation. Changes must be agreed upon and reflected in the frontend, backend, tests, and documentation.

## 2. General Rules

- Base path: `/api/v1`
- Transport: HTTPS in deployed environments.
- Request and response bodies use JSON unless otherwise stated.
- Authenticated endpoints require a valid Amazon Cognito access token using the configured API Gateway JWT authorizer.
- The player identity comes from trusted authorizer claims. Never trust a client-supplied player ID for ownership or scoring.
- Coordinates use decimal degrees: latitude and longitude.
- Timestamps use ISO 8601 UTC strings.
- The API validates request structure and configured limits. The worker independently validates route and polygon rules.
- Capture processing is asynchronous. A successful HTTP submission does not mean the territory has been captured.

## 3. Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/captures` | Submit a route for capture processing |
| `GET` | `/api/v1/captures/{captureId}` | Retrieve capture status and result |
| `GET` | `/api/v1/health` | Basic service health check |

The health endpoint must not expose secrets, tokens, internal configuration, or personal data.

## 4. Submit a Capture

### Request

`POST /api/v1/captures`

Headers:

- `Authorization: Bearer <access-token>`
- `Content-Type: application/json`
- `Idempotency-Key: <unique-client-generated-key>`

Example body:

```json
{
  "route": [
    {
      "latitude": 34.7025,
      "longitude": 135.4959,
      "timestamp": "2026-10-23T01:00:00Z",
      "accuracyMeters": 12.5
    },
    {
      "latitude": 34.7032,
      "longitude": 135.4971,
      "timestamp": "2026-10-23T01:00:15Z",
      "accuracyMeters": 10.0
    }
  ]
}
```

The example contains too few samples to guarantee a valid capture. It illustrates the payload format only.

### Request rules

- `route` is a required array of GPS samples.
- Each sample requires `latitude`, `longitude`, `timestamp`, and `accuracyMeters`.
- Latitude must be within `-90` to `90`; longitude must be within `-180` to `180`.
- Numeric values must be finite.
- Timestamps must parse correctly and satisfy the server's ordering and validation rules.
- `accuracyMeters` must be a non-negative finite number.
- The number of samples must not exceed the configured limit of 10,000.
- The server enforces body-size and request-rate limits.
- Unknown fields should be handled consistently; the initial implementation should reject unsupported fields unless the team explicitly decides otherwise.
- The client must not submit trusted ownership, score, area, or player identity fields.
- The server obtains player identity from authenticated authorizer claims.

### Responses

**`202 Accepted` — capture queued**

Return this only after the capture request has been durably recorded sufficiently for safe retries and the SQS enqueue operation has succeeded.

Example:

```json
{
  "captureId": "cap_example123",
  "status": "PENDING",
  "statusUrl": "/api/v1/captures/cap_example123"
}
```

A repeated request with the same idempotency key and the same authenticated player and request content should return or reference the existing logical capture, rather than create another one.

**`400 Bad Request` — malformed request**

Example:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request body is invalid."
  }
}
```

**`401 Unauthorized` — missing or invalid authentication**

**`409 Conflict` — idempotency key reused with different request content**

**`413 Content Too Large` — request body exceeds the configured limit**

**`429 Too Many Requests` — rate limit exceeded**

**`503 Service Unavailable` — the request cannot currently be accepted**

If queue submission fails, do not return `202 Accepted`. Ensure retries cannot create duplicate logical captures if the queue operation's outcome is uncertain.

## 5. Retrieve Capture Status

### Request

`GET /api/v1/captures/{captureId}`

The caller must be authenticated and authorized to view the requested capture. For the MVP, a player may retrieve their own capture records.

### Pending response

Example:

```json
{
  "captureId": "cap_example123",
  "status": "PROCESSING"
}
```

### Successful response

Example:

```json
{
  "captureId": "cap_example123",
  "status": "SUCCEEDED",
  "result": {
    "capturedAreaM2": 12500.0,
    "totalOwnedAreaM2": 48700.0
  }
}
```

- `capturedAreaM2` is the net area newly gained by this capture, not the full area enclosed by the route.
- `totalOwnedAreaM2` is the player's current net owned area after the capture.
- Values are examples only; the worker must calculate authoritative results.

### Rejected response

Example:

```json
{
  "captureId": "cap_example123",
  "status": "REJECTED",
  "error": {
    "code": "AREA_TOO_SMALL",
    "message": "The capture polygon is below the minimum area."
  }
}
```

### Failed response

Example:

```json
{
  "captureId": "cap_example123",
  "status": "FAILED",
  "error": {
    "code": "CAPTURE_PROCESSING_FAILED",
    "message": "The capture could not be processed."
  }
}
```

Do not expose stack traces, internal exception details, queue contents, or sensitive location data in error responses.

### Status retrieval rules

- Return `404 Not Found` if the capture does not exist or is not visible to the caller, according to the chosen privacy policy.
- The API must return the persisted status, not infer success from a queued message.
- A client should be able to retry status retrieval after network failure.
- Status and result schemas must be shared between frontend types and backend tests.

## 6. Capture Status Values

The proposed status values are:

| Status | Meaning |
|---|---|
| `PENDING` | Accepted and waiting for processing |
| `PROCESSING` | Being validated or processed |
| `SUCCEEDED` | Required ownership changes are durably committed |
| `REJECTED` | Route or geometry failed a validation rule |
| `FAILED` | Processing could not complete successfully |

The worker and persistence layer must define valid transitions and retry behavior. A transient infrastructure error should not automatically be treated as a permanent route rejection.

## 7. Error Codes

Use stable machine-readable error codes.

| Code | Meaning |
|---|---|
| `INVALID_REQUEST` | Request structure or fields are invalid |
| `INVALID_ROUTE` | Route data is invalid |
| `LOOP_NOT_CLOSED` | Route does not satisfy the closure rule |
| `ROUTE_TOO_SHORT` | Route does not meet the minimum distance or duration |
| `AREA_TOO_SMALL` | Polygon area is below the minimum |
| `GPS_DATA_INSUFFICIENT` | GPS accuracy, sample gaps, or sample data fail validation |
| `IDEMPOTENCY_KEY_CONFLICT` | A key was reused with different request content |
| `CAPTURE_PROCESSING_FAILED` | Processing could not complete |
| `RATE_LIMITED` | Request rate limit exceeded |
| `INTERNAL_ERROR` | Unexpected server-side failure |

Use appropriate HTTP status codes for synchronous request errors. Route-validation errors discovered asynchronously should appear in the final capture status.

Error messages are for display and diagnosis; clients should branch on error codes rather than message text.

## 8. Idempotency and Reliability

- The frontend generates an idempotency key for each logical capture submission.
- The API associates that key with the authenticated player and request content.
- Repeating the same logical request must not create duplicate ownership changes.
- Reusing a key with different content must be rejected.
- Persist enough request state to recover from uncertain queue-submission outcomes.
- SQS delivery is at least once; workers must be idempotent.
- A capture is `SUCCEEDED` only after the required ownership changes and result are durably committed.
- A lost HTTP response must not force the client to create a new logical capture.
- Define retention periods for idempotency records and capture history before production use.

## 9. Health Endpoint

`GET /api/v1/health`

Example response:

```json
{
  "status": "healthy"
}
```

The health endpoint is a minimal service-health indicator. Decide separately whether it should be publicly accessible or protected by the API gateway.

Do not include credentials, environment variables, internal hostnames, or personal data.

## 10. Implementation Boundaries

### API Lambda

- Parse and validate the HTTP request.
- Use trusted authorizer claims for player identity.
- Enforce request-size and sample-count limits.
- Implement idempotency and durable capture-request creation.
- Submit the processing message to SQS.
- Return `202 Accepted` only when queue submission is confirmed.
- Provide capture-status retrieval.

### Worker Lambda

- Validate route data and geometry independently.
- Apply the rules in `docs/GAME_RULES.md`.
- Calculate authoritative territory changes and net area.
- Handle duplicate messages, retries, and conflicting captures.
- Persist the final capture status and result consistently.

### Frontend

- Send the documented request shape.
- Generate and reuse an idempotency key when retrying the same logical submission.
- Show pending, successful, rejected, and failed states distinctly.
- Retrieve capture status after network interruptions.
- Never infer a successful capture merely because submission returned `202`.

## 11. Decisions to Finalize

Before implementation is considered complete, agree on:

1. Exact Cognito authorizer claims used for player identity.
2. Idempotency-key format, persistence, and retention.
3. Durable request creation and recovery if SQS submission has an uncertain outcome.
4. Exact response schema for each status and error.
5. Whether health checks are public.
6. Pagination and access rules for future capture-history and leaderboard endpoints.
7. Whether the capture result reports net gained area, enclosed polygon area, or both.

Do not add endpoints or fields independently without updating this contract and the relevant tests.
'@ | Set-Content -Path .\docs\API_CONTRACT.md -Encoding utf8

Write-Host "API_CONTRACT.md created."
