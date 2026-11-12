# Proposed changes to `API_CONTRACT.md`

> **DRAFT for review by the technical lead.** This file does not replace `docs/API_CONTRACT.md`.
> It lists what the implementation in `backend/api/` does where the contract is silent,
> inconsistent, or changed by the lead's latest decisions. Accept, change or reject each item;
> then the contract and the code can be updated together.
> Section numbers refer to the latest contract version the lead shared.

## 1. Decisions from the lead (now implemented)

| Decision | Implementation |
|---|---|
| Queue payload: gzip + base64 for the MVP, no S3 | `inline_route_store.py`, `sqs_queue.py`. The S3 adapter was removed from the branch (still in git history). `RouteStore` is kept as an interface so S3 can be added later |
| Hard size check after compression | `serialize_message` rejects a message over `MAX_MESSAGE_BYTES` (1 MiB) with `413`; `InlineRouteStore` rejects a payload over that limit minus 2 KiB |
| Test for the maximum-size route | `tests/test_inline_route_store.py` (10,000 realistic points and 10,000 random "worst case" points) |
| Worker idempotency by `captureId` | Documented in `docs/CAPTURE_RECORD_PROPOSAL.md` with conditional status transitions |
| Keep `handler.py` and `template.yaml` untouched | Both untouched. The wiring is in a separate module, `capture_lambda.py`; `handler.py` can call `lambda_handler` from it |

**Measured sizes** (10,000 samples, after gzip + base64):
about **134 KiB** for a realistic route and about **321 KiB** for the worst case (random points).
Both fit in 1 MiB; the worst case does **not** fit in the old 256 KiB limit. A queue created before
August 2025 may still be set to 256 KiB, so the queue's `MaximumMessageSize` must be set to
1 MiB (1048576) in the infrastructure.

## 2. Changes to the contract text

| Contract part | Proposed change |
|---|---|
| Section 4.3 (S3 claim-check) | Replace with the inline gzip + base64 payload below |
| Section 6.2 (error table) | Add `UNAUTHORIZED` (401), `CAPTURE_NOT_FOUND` (404), `NOT_FOUND` (404). Say which code goes with 413 and 503 (see section 5) |
| Section 10, item 6 (limits) | Set: minimum 4 samples, maximum 10,000, maximum request body 2,000,000 bytes |
| Section 4 (retry) | State: same key + same body -> the existing capture (`200`); same key + different body -> `409` |

## 3. SQS message (proposed)

```json
{
  "schemaVersion": 1,
  "captureId": "capture_0123456789abcdef0123456789abcdef",
  "playerId": "<verified JWT sub>",
  "route": { "encoding": "gzip+base64", "data": "H4sI..." }
}
```

`route.data` is base64 of the gzip of a JSON document with the **same shape as the request body**:

```json
{ "route": [ { "latitude": 34.7025, "longitude": 135.4959,
               "timestamp": "2026-10-23T01:00:00Z", "accuracyMeters": 10.0 } ] }
```

- Fields: `latitude` -90..90, `longitude` -180..180 (numbers), `timestamp` ISO 8601 UTC ending in
  `Z` and strictly increasing, `accuracyMeters` number >= 0. All four are required.
- The compression is deterministic (the same route always gives the same text).
- `playerId` always comes from the verified token, never from the client.
- Delivery is at-least-once; the worker must be idempotent by `captureId`.

## 4. Endpoint shapes (as implemented)

**`POST /api/v1/captures`** — headers `Authorization`, `Idempotency-Key` (8-128 chars, `A-Z a-z 0-9 _ -`).
Body `{ "route": [ ...samples ] }`; no other field is allowed.

| Result | Status | Body |
|---|---|---|
| Accepted now | `202` | `{"captureId": "...", "status": "PENDING", "statusUrl": "/api/v1/captures/<id>"}` |
| Same key, same body (retry) | `200` | same fields; `status` is the current status |
| Same key, different body | `409` | error `IDEMPOTENCY_KEY_CONFLICT` |

`202` is returned only after the queue accepted the message. `captureId` is `capture_` + 32 hex
characters derived from the player and the key.

**`GET /api/v1/captures/{captureId}`** -> `200`
`{"captureId", "status", "createdAt", "updatedAt"}` plus `result` when `SUCCEEDED`, or `error`
(`code`, `message`) when `REJECTED` / `FAILED`. A missing capture and another player's capture both
return `404 CAPTURE_NOT_FOUND`. A capture that is still internal (`RECEIVED`) also returns `404`.
The shapes of `result` and `error` come from the worker and are **not agreed yet**.

**`GET /api/v1/health`** -> `200 {"status": "healthy"}`, no authentication in this code.
The lead has a separate implementation on `feature/api-health-check`; the route in `http_api.py`
can be removed if the lead prefers that one.

**Error body (all errors from the API code):**
`{"error": {"code": "<CODE>", "message": "<text>"}}`. `401` from the API Gateway authorizer has its
own format and is outside this code.

## 5. Error codes and status (proposed table)

| Situation | Status | Code |
|---|---|---|
| Not JSON, missing or wrong-type field, coordinate out of range, bad timestamp or order, fewer than 4 samples, unsupported field, bad `Idempotency-Key` | 400 | `INVALID_REQUEST` |
| **More than 10,000 samples**, body over 2,000,000 bytes, or route too large after compression | 413 | `INVALID_REQUEST` (the contract's 413 example uses this code; the message tells which limit) |
| No verified identity | 401 | `UNAUTHORIZED` |
| Missing or foreign capture, or still `RECEIVED` | 404 | `CAPTURE_NOT_FOUND` |
| Path or method the API does not handle | 404 | `NOT_FOUND` |
| Same key, different body | 409 | `IDEMPOTENCY_KEY_CONFLICT` |
| Database or queue unavailable (nothing accepted; retry with the same key) | 503 | `INTERNAL_ERROR` (the contract's 503 example uses this code) |
| Unexpected error | 500 | `INTERNAL_ERROR` |

`INVALID_ROUTE` is not used by the API; it stays for the worker's route and geometry rules.
If a separate code for 413 or 503 is wanted (`PAYLOAD_TOO_LARGE`, `SERVICE_UNAVAILABLE`), that is a
contract change; the code needs only a one-line change in `errors.py` and its tests.

## 6. What the infrastructure must provide (not created here)

- SQS queue with `MaximumMessageSize` of 1048576, and the worker's event source mapping for 1 MiB.
- API Lambda permissions: DynamoDB `GetItem`, `PutItem`, `UpdateItem` on the capture table;
  SQS `SendMessage` on the queue. No S3 permission is needed for the API any more.
- Environment variables (names proposed): `CAPTURE_QUEUE_URL`, `CAPTURES_TABLE_NAME`.
- Authorizer, CORS, throttling, and a dead-letter queue.

## 7. Open points for the worker owner

1. Format of `result` and `error` written to the table (see `docs/CAPTURE_RECORD_PROPOSAL.md`).
2. Conditional status transitions and the `RECEIVED` / `PENDING` race (see `docs/CAPTURE_RECORD_PROPOSAL.md`).
3. Reading the compressed route: base64 decode, then gunzip, then JSON (`unpack_route` in
   `inline_route_store.py` is a reference).

## 8. Housekeeping (not changed in this PR)

On `main`, `docs/API_CONTRACT.md` and `docs/DATA_MODEL.md` both begin with a line `@'` and end with
`'@ | Set-Content -Path ... -Encoding utf8` and `Write-Host "... created."`. These are leftovers of a
PowerShell script that wrote the files and are not part of the documents. They are harmless but
should be removed by the owner. `docs/DATA_MODEL.md` also still describes route chunks stored in
DynamoDB (section 6); the lead's gzip + base64 decision replaces that (see
`docs/CAPTURE_RECORD_PROPOSAL.md`, section 2a).
