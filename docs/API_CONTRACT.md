# ConquestRunner — API Contract

**Status:** MVP contract — core decisions confirmed by the technical lead; integration with the map client still to be verified  
**Scope:** Initial HTTP API for ConquestRunner  
**Last updated:** 2026-11-16

---

## 1. Purpose

This document defines the initial HTTP API for the ConquestRunner MVP.

The API accepts authenticated capture requests, queues them for asynchronous processing, and exposes capture status.

The backend is the source of truth for route validity, territory ownership, and scores. The frontend must not independently determine or persist authoritative ownership changes.

This is the contract for implementation. Sections marked **Decided** were confirmed by the technical lead. Items marked **Proposed** or listed in section 10.2 still need agreement. Changes must be agreed upon and reflected in the frontend, backend, tests, and documentation.

---

## 2. General Rules

- Base path: `/api/v1`
- Transport: HTTPS in deployed environments.
- Request and response bodies use JSON unless otherwise stated.
- Authenticated endpoints require a valid Amazon Cognito access token using the configured API Gateway JWT authorizer.
- The player identity comes from trusted authorizer claims. Never trust a client-supplied player ID for ownership or scoring.
- Coordinates use decimal degrees: latitude and longitude.
- Timestamps use ISO 8601 UTC strings ending in `Z`.
- The API validates request structure and configured limits. The worker independently validates route and polygon rules.
- Capture processing is asynchronous. A successful HTTP submission does not mean the territory has been captured.
- GPS route samples are private player data. They must not be exposed through public endpoints or unnecessarily included in logs.
- The API and worker must handle retries and duplicate processing safely.
- **Decided:** the server recalculates all route metrics (start and end time, distance, duration, area, speed) from the samples. The client must not send summary values.
- **Decided:** the request accepts only the documented fields. Any other field is rejected with `400`.

---

## 3. Endpoints

| Method | Path | Purpose | Authentication |
|---|---|---|---|
| `POST` | `/api/v1/captures` | Submit a route for capture processing | Required |
| `GET` | `/api/v1/captures/{captureId}` | Retrieve capture status and result | Required |
| `GET` | `/api/v1/health` | Basic service health check | None in the current implementation (to be confirmed) |

The health endpoint must not expose secrets, tokens, internal configuration, or personal data.

---

## 4. Submit a Capture

### 4.1 Request

`POST /api/v1/captures`

Headers:

```http
Authorization: Bearer <access-token>
Content-Type: application/json
Idempotency-Key: <unique-client-generated-key>
```

The `Idempotency-Key` identifies one logical capture submission. The frontend must reuse the same key when retrying the same submission.

**Decided:** the map client generates one id for each recorded route (`clientRouteId`, for example a UUID) and sends it as the `Idempotency-Key` header. It is **not** sent in the body. The key must be 8 to 128 characters: letters, digits, `-` and `_`.

Example request body:

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

The body contains **only** `route`. The example contains too few samples to be accepted (at least 4 are required). It illustrates the payload format only.

### 4.2 Request Rules

- The body is a JSON object with exactly one field, `route`. **Decided:** any other top-level field is rejected with `400` (for example `playerId`, `score`, `areaM2`, `schemaVersion`, `clientRouteId`, `startedAt`, `endedAt`, `clientSummary`).
- `route` is a required array of GPS samples.
- Each sample requires exactly these fields, and no others:
  - `latitude`
  - `longitude`
  - `timestamp`
  - `accuracyMeters`
- **Decided:** optional GPS fields (`altitude`, `heading`, `speed`) are **not accepted** in the MVP. A sample that contains them is rejected with `400`. This keeps the payload small and limits privacy exposure; the server derives speed from the samples.
- Latitude must be within `-90` to `90`.
- Longitude must be within `-180` to `180`.
- Numeric values must be finite numbers (not strings, not booleans).
- `timestamp` is an ISO 8601 UTC string ending in `Z` (milliseconds are allowed, for example `2026-10-23T01:00:00.123Z`). Timestamps must be **strictly increasing**.
- `accuracyMeters` must be a non-negative finite number.
- The number of samples must be **at least 4** and **at most 10,000**. More than 10,000 returns `413`.
- The request body must not exceed **2,000,000 bytes**. A larger body returns `413`.
- The server also enforces request-rate limits (API Gateway throttling).
- Structural validation happens before the request is accepted for processing.
- Route geometry, loop closure, distance, area, speed and ownership validation are performed by the worker according to `docs/GAME_RULES.md`.

The values 4 samples and 2,000,000 bytes are the current implementation limits and are configurable.

### 4.3 Route Payload in the Queue Message — gzip + base64

**Decided (technical lead, MVP):** the route is sent inside the SQS message, compressed with gzip and encoded with base64. S3 is **not** used for the MVP. It can be added later behind the same interface.

A route of 10,000 samples is about 1 MB of JSON. After gzip and base64 it measured about 134 KiB for a realistic route and about 321 KiB for the worst case (random points). Amazon SQS allows messages up to 1 MiB, so the queue's `MaximumMessageSize` must be set to **1048576** (a queue created before August 2025 may still be set to 256 KiB). The API checks the size again after compression and rejects a message over the limit with `413`.

**Flow:**

1. API Lambda receives and validates the HTTP request.
2. API Lambda obtains the player identity from trusted Cognito authorizer claims.
3. API Lambda derives the `captureId` from the player and the `Idempotency-Key`, and creates the durable capture record with a **conditional write** (`RECEIVED`, internal). A second request with the same key cannot create a second record.
4. API Lambda packs the route: JSON, then gzip, then base64.
5. API Lambda sends **one** message to SQS.
6. API Lambda marks the record `PENDING` and returns `202 Accepted`.
7. Worker Lambda receives the message, decodes the route (base64, gunzip, JSON), validates the geometry and processes the ownership changes.
8. Capture status and result are persisted.

**SQS message format (Proposed, to be agreed with the worker owner):**

```json
{
  "schemaVersion": 1,
  "captureId": "capture_0123456789abcdef0123456789abcdef",
  "playerId": "<verified JWT sub>",
  "route": { "encoding": "gzip+base64", "data": "H4sI..." }
}
```

`route.data` is the base64 of the gzip of a JSON document with the same shape as the request body:

```json
{ "route": [ { "latitude": 34.7025, "longitude": 135.4959, "timestamp": "2026-10-23T01:00:00Z", "accuracyMeters": 12.5 } ] }
```

Notes:

- `captureId` is the stable identifier of the logical capture (`capture_` followed by 32 hexadecimal characters).
- `playerId` is derived from the trusted authentication context, never from the request body.
- The compression is deterministic: the same route always produces the same text, so a retry sends an identical message.
- The message contains private GPS data. The queue and its dead-letter queue must be encrypted and restricted, retention must be agreed, and message bodies must never be logged.
- SQS delivery is at least once. The worker must treat `captureId` as an idempotency key.

### 4.4 Successful Response

**`202 Accepted` — capture queued**

Return this only after the capture request has been durably recorded sufficiently for safe retries and the SQS enqueue operation has succeeded.

Example:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
```

```json
{
  "captureId": "capture_abc123",
  "status": "PENDING",
  "statusUrl": "/api/v1/captures/capture_abc123"
}
```

A `202 Accepted` response means the capture was accepted for asynchronous processing. It does not mean the capture succeeded.

**`200 OK` — the same request was already accepted (retry)**

**Decided:** the same player, the same `Idempotency-Key` and the same request body return the **existing** capture. No second capture is created. The body has the same fields as `202`, and `status` is the current status (it can already be `PROCESSING` or a final status):

```json
{
  "captureId": "capture_abc123",
  "status": "PROCESSING",
  "statusUrl": "/api/v1/captures/capture_abc123"
}
```

### 4.5 Error Responses

**`400 Bad Request` — malformed request**

The request body is missing required fields, contains invalid data types, or is malformed JSON.

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

The request does not contain a valid access token.

Example:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication is required."
  }
}
```

**`409 Conflict` — idempotency key reused with different request content**

A key already associated with a logical capture is submitted with different content by the same authenticated player.

Example:

```json
{
  "error": {
    "code": "IDEMPOTENCY_KEY_CONFLICT",
    "message": "The idempotency key is already associated with a different request."
  }
}
```

**`413 Content Too Large` — request body exceeds the configured limit**

Returned when the body is larger than 2,000,000 bytes, the route has more than 10,000 samples, or the route is still too large after compression. The code is `INVALID_REQUEST`; the message tells which limit was exceeded.

Example:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request body exceeds the configured size limit."
  }
}
```

**`429 Too Many Requests` — request rate limit exceeded**

Example:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please try again later."
  }
}
```

**`503 Service Unavailable` — the request cannot currently be accepted**

This may occur when durable storage or queue submission fails.

Example:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "The capture request could not be accepted at this time."
  }
}
```

If queue submission fails, do not return `202 Accepted`. Ensure retries cannot create duplicate logical captures if the queue operation's outcome is uncertain.

**`500 Internal Server Error` — unexpected error**

The body uses code `INTERNAL_ERROR` and a generic message. No stack trace, exception text or GPS data is ever returned.

### 4.6 Status Codes: Meaning and Client Behavior

**Decided:** these status codes and their retry behavior apply to `POST /api/v1/captures`. Rule for every retry: **always reuse the same `Idempotency-Key` for the same recorded route.** Never create a new key for the same route, because that would be a second capture.

| Status | Code | Meaning | Client behavior |
|---|---|---|---|
| `202` | — | Accepted for processing for the first time. Not captured yet | Poll the status. Do not show success |
| `200` | — | This request was already accepted. The body shows the current status | Continue polling. No new capture exists |
| `400` | `INVALID_REQUEST` | Malformed JSON, missing or wrong field, value out of range, unsupported field, timestamps not increasing, fewer than 4 samples, or a bad `Idempotency-Key` | A client data bug. Do not retry unchanged. Fix the data |
| `401` | `UNAUTHORIZED` | Missing or invalid access token (the body may be produced by the API Gateway authorizer and can differ) | Refresh the token or sign in again, then retry with the same key |
| `409` | `IDEMPOTENCY_KEY_CONFLICT` | The same key was already used with a different body | A client bug. A different route needs a new key. Do not retry |
| `413` | `INVALID_REQUEST` | More than 10,000 samples, body over 2,000,000 bytes, or too large after compression | Do not retry unchanged. Reduce the number of samples |
| `429` | `RATE_LIMITED` | Request rate limit exceeded | Wait, then retry with the same key |
| `503` | `INTERNAL_ERROR` | Nothing was accepted: the database or the queue is unavailable | Retry with the **same** key after a short wait (for example 1, 2 and 4 seconds, then stop and tell the user) |
| `500` | `INTERNAL_ERROR` | Unexpected error | Retry later with the same key. If it persists, report it |

---

## 5. Retrieve Capture Status

### 5.1 Request

`GET /api/v1/captures/{captureId}`

Headers:

```http
Authorization: Bearer <access-token>
```

The endpoint must verify that the authenticated player is authorized to access the requested capture.

A player must not be able to retrieve another player's private capture status or route data.

### 5.2 Capture Statuses

The capture lifecycle uses the following statuses:

| Status | Meaning |
|---|---|
| `PENDING` | Capture accepted and waiting for processing |
| `PROCESSING` | Worker is processing the capture |
| `SUCCEEDED` | Ownership changes and result have been durably committed |
| `REJECTED` | Route or game rules rejected the capture |
| `FAILED` | Processing failed due to an internal or operational error |

The API also keeps an internal state, `RECEIVED` (stored but not yet accepted by the queue). It is never returned to clients: reading it gives `404` (see 5.8).

The exact persistence and transition rules must be aligned with `docs/GAME_RULES.md` and `docs/DATA_MODEL.md`.

### 5.3 Pending Response

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "captureId": "capture_abc123",
  "status": "PENDING",
  "createdAt": "2026-10-23T01:00:30Z",
  "updatedAt": "2026-10-23T01:00:30Z"
}
```

### 5.4 Processing Response

```json
{
  "captureId": "capture_abc123",
  "status": "PROCESSING",
  "createdAt": "2026-10-23T01:00:30Z",
  "updatedAt": "2026-10-23T01:00:35Z"
}
```

### 5.5 Successful Response

```json
{
  "captureId": "capture_abc123",
  "status": "SUCCEEDED",
  "createdAt": "2026-10-23T01:00:30Z",
  "updatedAt": "2026-10-23T01:00:40Z",
  "result": {
    "capturedAreaM2": 1250.5,
    "totalOwnedAreaM2": 8500.0
  }
}
```

Definitions:

- `capturedAreaM2`: net newly gained area resulting from this capture.
- `totalOwnedAreaM2`: the player's current total owned area after the capture.

Score is based on current net owned area, not cumulative historical captured area.

### 5.6 Rejected Response

```json
{
  "captureId": "capture_abc123",
  "status": "REJECTED",
  "createdAt": "2026-10-23T01:00:30Z",
  "updatedAt": "2026-10-23T01:00:40Z",
  "error": {
    "code": "LOOP_NOT_CLOSED",
    "message": "The submitted route does not form a valid closed loop."
  }
}
```

### 5.7 Failed Response

```json
{
  "captureId": "capture_abc123",
  "status": "FAILED",
  "createdAt": "2026-10-23T01:00:30Z",
  "updatedAt": "2026-10-23T01:00:40Z",
  "error": {
    "code": "CAPTURE_PROCESSING_FAILED",
    "message": "Capture processing could not be completed."
  }
}
```

### 5.8 Not Found / Unauthorized

**Decided:** a capture that does not exist, a capture that belongs to another player, and a capture that is still internal (`RECEIVED`) all return the same response, so another player's capture cannot be discovered:

```http
HTTP/1.1 404 Not Found
```

```json
{
  "error": {
    "code": "CAPTURE_NOT_FOUND",
    "message": "The capture was not found."
  }
}
```

A missing or invalid token returns `401` as in section 4.5. A path or method the API does not handle returns `404` with code `NOT_FOUND`.

---

## 6. Response and Error Format

### 6.1 General Error Format

Errors should use a consistent JSON structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation."
  }
}
```

Error messages are for display and diagnosis. Clients should branch on error codes rather than message text.

### 6.2 Error Codes

| Code | HTTP status | Meaning |
|---|---|---|
| `INVALID_REQUEST` | 400, 413 | Request structure or fields are invalid, or a size limit was exceeded |
| `UNAUTHORIZED` | 401 | Authentication is missing or invalid |
| `CAPTURE_NOT_FOUND` | 404 | The capture does not exist or is not visible to the caller |
| `NOT_FOUND` | 404 | The path or method is not handled by the API |
| `IDEMPOTENCY_KEY_CONFLICT` | 409 | A key was reused with different request content |
| `RATE_LIMITED` | 429 | Request rate limit exceeded |
| `INTERNAL_ERROR` | 500, 503 | Unexpected internal error, or the request could not be accepted at this time |
| `INVALID_ROUTE` | (status `REJECTED`) | Route or polygon geometry is invalid (set by the worker) |
| `LOOP_NOT_CLOSED` | (status `REJECTED`) | Route does not form a valid closed loop |
| `ROUTE_TOO_SHORT` | (status `REJECTED`) | Route distance is below the configured minimum |
| `AREA_TOO_SMALL` | (status `REJECTED`) | Polygon area is below the configured minimum |
| `GPS_DATA_INSUFFICIENT` | (status `REJECTED`) | GPS accuracy, sample gaps, timestamps, or sample data fail validation |
| `CAPTURE_PROCESSING_FAILED` | (status `FAILED`) | Processing could not complete |

Codes with an HTTP status are returned directly by the API. The worker's codes appear inside the `error` object of a `REJECTED` or `FAILED` capture status (section 5). The API itself does not use `INVALID_ROUTE`.

The final set of error codes and their HTTP status mappings must be consistent between the API handler, worker, frontend, and tests.

---

## 7. Idempotency and Reliability

- The frontend generates an idempotency key for each logical capture submission (the map client uses its `clientRouteId`).
- The frontend reuses the same key when retrying that submission.
- **Decided:** the server must prevent duplicate captures **atomically**. The `captureId` is derived from the authenticated player and the key, and the capture record is created with a conditional write that fails if the record already exists. Two concurrent requests with the same key therefore cannot create two captures.
- Same player + same key + same body: the existing capture is returned (`200`).
- Same player + same key + different body: `409`. The server stores a hash of the route to detect this.
- A key belongs to the player who used it. Another player's identical key creates a different capture.
- Repeating the same logical request must not create duplicate ownership changes.
- The backend must persist enough request state to recover from uncertain queue-submission outcomes.
- SQS delivery is at least once; workers must be idempotent by `captureId`, using conditional state transitions.
- A capture is `SUCCEEDED` only after the required ownership changes and result are durably committed.
- A lost HTTP response must not force the client to create a new logical capture.
- Define retention periods for idempotency records and capture history before production use.

### 7.1 Queue and Database Failure Considerations

The API submission workflow is: record (`RECEIVED`), pack the route, send one message, mark `PENDING`. DynamoDB and SQS do not share a single atomic transaction, so every step is safe to repeat and the client recovers by retrying with the same key.

| Failure | Result | Recovery |
|---|---|---|
| The record cannot be created (database error) | `503`. Nothing is stored or sent | Retry with the same key |
| The record exists, the message is not sent (queue error) | `503`, never `202`. The record stays `RECEIVED` and is not visible | Retry with the same key. The steps are repeated |
| The message is sent, marking `PENDING` fails | `503`. The message is already in the queue | A retry may send a duplicate message. The worker must ignore it |
| The queue send outcome is uncertain | Same as above | A retry may duplicate the message; no second capture is created |
| The route is too large after compression | `413` | Reduce the number of samples. Retrying unchanged gives the same result |
| SQS delivers the same message several times | The worker must process idempotently | Conditional status transitions on the capture record |
| The worker receives the message while the record is still `RECEIVED` | Possible: the message is sent before `PENDING` is written | The worker accepts both `RECEIVED` and `PENDING` as a start. The API's `PENDING` update is conditional and never overwrites the worker's progress |
| The worker crashes during processing | The worker's retry must not partially duplicate ownership changes | Worker design |
| The worker commits a result but fails before acknowledging the message | A duplicate delivery must not apply the changes again | Conditional transitions |
| The client never retries after a failure | A `RECEIVED` record stays behind | Cleanup is not designed yet (section 10.2) |

The route exists only in the queue message (and in the dead-letter queue if processing keeps failing), so the retention of those queues is the retention of the route.

---

## 8. Health Endpoint

### 8.1 Request

`GET /api/v1/health`

Authentication: none in the current implementation (to be confirmed).

### 8.2 Successful Response

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "status": "healthy"
}
```

The health endpoint should return a minimal response and must not expose:

- Secrets or environment variables
- JWTs or authorization headers
- Private GPS data
- Internal infrastructure details
- Player information

The initial MVP health endpoint indicates that the API handler is responding. Whether it should also check dependencies such as DynamoDB or SQS is a separate decision.

---

## 9. Implementation Responsibilities

### 9.1 API Lambda

The API Lambda is responsible for:

- Handling HTTP requests.
- Using trusted authorizer claims for player identity.
- Enforcing request-size and sample-count limits.
- Validating request structure and field types.
- Implementing idempotency and durable capture-request creation.
- Packing the route (gzip + base64) into the queue message and checking the final message size.
- Submitting the processing message to SQS.
- Returning `202 Accepted` only when queue submission is confirmed.
- Providing capture-status retrieval.
- Returning consistent errors.
- Avoiding expensive polygon-intersection calculations.

### 9.2 Worker Lambda

The worker Lambda is responsible for:

- Decoding the route from the queue message (base64, gunzip, JSON).
- Applying the rules in `docs/GAME_RULES.md`.
- Independently validating route geometry and capture eligibility.
- Calculating authoritative territory changes and net area.
- Handling duplicate messages, retries, and conflicting captures.
- Persisting the final capture status and result consistently.
- Ensuring a capture is not reported as successful before ownership changes are durable.

### 9.3 Frontend

The frontend is responsible for:

- Sending the documented request shape: only `route`, with samples of exactly four fields.
- Sending its `clientRouteId` as the `Idempotency-Key` header, not in the body.
- Generating one idempotency key per recorded route and reusing it for every retry of that route (see section 4.6).
- Displaying pending, successful, rejected, and failed states distinctly.
- Retrieving capture status after network interruptions.
- Treating backend ownership and score results as authoritative.
- Never trusting local calculations as the final score or territory ownership result.

---

## 10. Decisions

### 10.1 Decided (confirmed by the technical lead)

1. The request body is `{ "route": [...] }`. The server recalculates the route metrics. `schemaVersion`, `startedAt`, `endedAt` and `clientSummary` are not sent.
2. The map client's `clientRouteId` is sent as the `Idempotency-Key` header. The same key is reused for retries, and the server prevents duplicate captures atomically.
3. Optional GPS fields (`altitude`, `heading`, `speed`) are excluded for the MVP.
4. Response status codes `202`, `200`, `400`, `401`, `409`, `413` and `503`, with the meanings and retry behavior in section 4.6.
5. The route is sent in the SQS message as gzip + base64. S3 is not used for the MVP.
6. The worker must handle duplicate SQS messages idempotently by `captureId`, using conditional state transitions or an equivalent safe mechanism.

### 10.2 Still required

The following must be agreed and documented before full integration or production deployment:

1. Exact Cognito authorizer claims used for player identity (the API currently uses the `sub` claim).
2. Retention of idempotency records and capture records, and cleanup of captures left in `RECEIVED`.
3. Exact response schema for `result` and `error` of each status (the worker owner).
4. Whether health checks are public, and whether they check dependencies.
5. Request-rate limits, and confirmation of the request body limit (2,000,000 bytes) and the minimum of 4 samples.
6. Exact SQS message schema and versioning, queue `MaximumMessageSize` (1048576), encryption, dead-letter queue and retention.
7. Worker retry and reconciliation behavior.
8. Atomicity and recovery strategy for ownership changes and capture status.
9. Verification of the HTTP status mappings (section 6.2) in an integrated test with the map client.

These decisions must be recorded in the relevant documents rather than independently invented by frontend and backend contributors.

---

## 11. Related Documents

- `docs/ARCHITECTURE.md` — system components and engineering boundaries.
- `docs/GAME_RULES.md` — validation, ownership, and scoring behavior.
- `docs/API_CONTRACT.md` — HTTP interface and error behavior.
- `docs/DATA_MODEL.md` — persistence schemas and access patterns.
- `docs/CONTRIBUTING.md` — Git workflow, code review, and development rules.
- `docs/API_CONTRACT_CHANGES.md` — what the API implementation does where this contract was silent, and the changes made in this update.
- `docs/CAPTURE_RECORD_PROPOSAL.md` — the capture record used by the capture API and how it differs from `docs/DATA_MODEL.md`.

Update the relevant document and tests whenever a shared decision changes.
