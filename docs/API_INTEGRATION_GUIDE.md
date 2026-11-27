# Capture API: integration guide for the map / GPS client

> **Status: confirmed by the technical lead for the MVP.** It follows `docs/API_CONTRACT.md`
> (updated in PR #2, sections 4 and 10.1) and what is implemented in `backend/api/`. The first
> integration test with the map client is still to be done, and nothing has been run against real
> AWS yet. More details: `docs/API_CONTRACT_CHANGES.md` in PR #2.

## 1. Request: `POST /api/v1/captures`

Headers: `Authorization: Bearer <Cognito access token>`, `Content-Type: application/json`,
`Idempotency-Key: <id>` (8 to 128 characters: letters, digits, `-`, `_`; a UUID works).

Body: **exactly** this, no other field:

```json
{
  "route": [
    { "latitude": 34.7025123, "longitude": 135.4959456,
      "timestamp": "2026-10-23T01:00:00.123Z", "accuracyMeters": 12.5 }
  ]
}
```

| Rule | Value |
|---|---|
| Samples | at least 4, at most 10,000 |
| `latitude` / `longitude` | numbers, -90..90 / -180..180 |
| `timestamp` | ISO 8601 UTC string **ending in `Z`**, strictly increasing (milliseconds are fine) |
| `accuracyMeters` | number, 0 or more, **required** |
| Body size | at most 2,000,000 bytes |
| Unknown fields | rejected with `400` (at the top level and inside each sample) |

Making the samples from the browser Geolocation API:
- `timestamp`: `new Date(position.timestamp).toISOString()` (always ends in `Z`).
- `accuracyMeters`: `position.coords.accuracy`.
- Drop a sample whose timestamp is not later than the previous one (`watchPosition` can repeat times).
- Round coordinates to 7 decimals (about 1 cm). It keeps the body small.

## 2. Mapping from the current map payload

| Map payload today | Proposed | Why |
|---|---|---|
| `samples` | rename to `route` | Contract field name |
| `clientRouteId` | send it as the **`Idempotency-Key` header**, not in the body | One id per recorded route, reused on every retry (see section 3) |
| `schemaVersion` | do not send | Not part of the contract (decided) |
| `startedAt` / `endedAt` | do not send | The server uses the first and last sample times |
| `clientSummary` | do not send | The server recalculates everything; client values are never trusted |
| `altitude`, `heading`, `speed` per sample | do not send | **Decided:** excluded for the MVP (not needed for ownership, the server derives speed, less payload and privacy exposure). A sample that contains them is rejected with `400` |

## 3. Idempotency and retries

- Create **one** id when the run is recorded (for example `crypto.randomUUID()`), store it with the
  route, and send it as `Idempotency-Key` on **every** attempt for that route.
- Same id + same body: the existing capture (`200`). Same id + different body: `409`.
- The server derives `captureId` from the player and this id; use the `captureId` in the response
  for status checks. The map client never sends a `captureId`.
- A lost response, a `503`, or a network error: retry with the **same** id. Never make a new id for
  the same route (that would be a second capture).

## 4. Responses and what to do

| Status | Body | Client action |
|---|---|---|
| `202` | `{"captureId", "status": "PENDING", "statusUrl"}` | Accepted for processing. **Not** a capture yet: poll the status |
| `200` | same fields, `status` is the current one | This route was already accepted: continue polling |
| `400` | `{"error": {"code": "INVALID_REQUEST", "message"}}` | A bug in the client data. Show a generic error; do not retry unchanged |
| `401` | from API Gateway, **different body** | Refresh the token or ask the user to sign in |
| `409` | `IDEMPOTENCY_KEY_CONFLICT` | The same id was used with another route: a client bug |
| `413` | `INVALID_REQUEST` | Route too large (over 10,000 samples or 2 MB): thin out samples |
| `503` | `INTERNAL_ERROR` | Nothing was accepted. Retry with the **same** id after a short wait |
| `500` | `INTERNAL_ERROR` | Retry later with the same id |

Status check: `GET /api/v1/captures/{captureId}` returns
`{"captureId", "status", "createdAt", "updatedAt"}` plus `result` (`SUCCEEDED`) or `error`
(`REJECTED` / `FAILED`). Statuses: `PENDING`, `PROCESSING`, `SUCCEEDED`, `REJECTED`, `FAILED`.
Poll every 2 to 3 seconds and stop on a final status. `404 CAPTURE_NOT_FOUND` means the id is
unknown or belongs to someone else. The shapes of `result` and `error` come from the worker and
are **not agreed yet**: treat them as optional and show `error.message` as is.

## 5. TypeScript types (a starting point)

```ts
export interface GpsSample {
  latitude: number;
  longitude: number;
  timestamp: string; // ISO 8601 UTC, ends with Z
  accuracyMeters: number;
}

export interface CaptureRequest {
  route: GpsSample[];
}

export type CaptureStatus = "PENDING" | "PROCESSING" | "SUCCEEDED" | "REJECTED" | "FAILED";

export interface CaptureAccepted {
  captureId: string;
  status: CaptureStatus;
  statusUrl: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface CaptureStatusResponse {
  captureId: string;
  status: CaptureStatus;
  createdAt: string;
  updatedAt: string;
  result?: Record<string, number>; // shape not agreed yet
  error?: { code: string; message: string };
}
```

## 6. Decided and still open

Decided by the lead:
1. The body is `{ "route": [...] }` only; the server recalculates the route metrics.
2. `clientRouteId` is sent as the `Idempotency-Key` header and reused on every retry; the server
   prevents duplicate captures atomically.
3. `altitude`, `heading` and `speed` are excluded for the MVP.
4. Status codes `202`, `200`, `400`, `401`, `409`, `413`, `503` as in section 4.

Still open: the shapes of `result` and `error` (worker owner), and the integration test with the
map client. If the map client cannot follow this guide, tell the lead before changing the payload.
