# ConquestRunner — Worker Contract (API side)

> **Status: DRAFT, second revision. Not agreed by the team.** Nothing here is implemented in
> `backend/worker/` (all worker files are still empty placeholders) and nothing was run on AWS.
>
> This document describes the boundary between the capture API and the worker, precisely enough to
> implement the worker side. It is **not** a design of the territory logic or of the game result. Those
> decisions, and the GPS plausibility thresholds, belong to the team and are listed in section 10.

Every statement carries one label:

| Label | Meaning |
|---|---|
| **[EXISTING]** | The API code in `backend/api/` already does or requires this. It is covered by local tests with in-memory fakes. It is **not** verified on real AWS |
| **[PROPOSAL]** | Suggested worker behavior. It is not implemented and the team may change it |
| **[OPEN]** | A decision nobody has made yet. This document does not make it |

**Changes from the first draft:** the processing lease is now a numeric attribute instead of a
comparison of `updatedAt` strings; an attempt token is part of the proposal; the final status and the
`result`/`error` are written in one conditional write; section 2 and 3 now follow the code exactly; the
rules for what `result`/`error` may contain are added.

---

## 1. Where the worker sits

```
client -> API Gateway -> API Lambda -> DynamoDB (record) + SQS (one message) -> worker Lambda -> DynamoDB
```

The API Lambda accepts a route, stores a capture record and sends one SQS message. The worker reads that
message, checks and processes the route, and writes the final state to the same DynamoDB record. The
client only talks to the API and polls `GET /api/v1/captures/{captureId}`.

## 2. The SQS message [EXISTING]

The API calls `send_message` with **only** `QueueUrl` and `MessageBody`. No message attributes, no group
id, no delay. The body is compact JSON text (from `serialize_message` in `backend/api/sqs_queue.py`):

```json
{
  "schemaVersion": 1,
  "captureId": "capture_<32 hex characters>",
  "playerId": "<cognito sub>",
  "route": { "encoding": "gzip+base64", "data": "<base64 text>" }
}
```

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | number | `1` today |
| `captureId` | string | `capture_` plus 32 hex characters. The primary identifier of the capture |
| `playerId` | string | The Cognito `sub` from the verified token. Never taken from the client |
| `route.encoding` | string | `gzip+base64` is the only value today |
| `route.data` | string | ASCII, standard base64 alphabet with padding |

Maximum message size: 1 MiB (the API refuses to send more).

**Decoding steps** (the same as `unpack_route` in `backend/api/inline_route_store.py`):

1. Check `route.encoding == "gzip+base64"`. Anything else cannot be read.
2. Base64-decode `route.data` strictly (reject characters outside the alphabet).
3. Gzip-decompress the bytes.
4. Parse the result as UTF-8 JSON.

**Decoded route document:**

```json
{
  "route": [
    { "latitude": 35.0001, "longitude": 135.0001,
      "timestamp": "2026-11-24T02:00:01.000Z", "accuracyMeters": 10 }
  ]
}
```

(Fake values, for the shape only.)

- `route` is a list of 4 to 10,000 samples, each with exactly `latitude`, `longitude`, `timestamp`,
  `accuracyMeters`.
- The API has already checked: all four fields are present, the numbers are finite and in range, the
  timestamps are strictly increasing, and there are no other fields.
- `timestamp` is an ISO 8601 UTC string ending in `Z`. Parse it with a real ISO 8601 parser and do not
  assume a fixed number of fractional digits.
- The API has **not** checked plausibility: speed, jumps between points, accuracy limits, route length,
  closed loops. That is the worker's job and its thresholds are **[OPEN]** (section 10).
- The route is **not** stored anywhere else. If the message is lost, the route is lost.

## 3. The DynamoDB capture record

### 3.1 Attributes the API writes and reads [EXISTING]

Table: one item per capture. Keys: `PK = "CAPTURE#<captureId>"` (String), `SK = "META"` (String).

| Attribute | Type | Written by | Rule |
|---|---|---|---|
| `PK`, `SK` | S | API | Never change them |
| `captureId` | S | API | Never change it |
| `playerId` | S | API | Never change it. The API treats a capture whose `playerId` is not the caller as "not found" |
| `requestHash` | S | API | SHA-256 of the route, used to detect reuse of an `Idempotency-Key`. Never change it |
| `status` | S | API, then worker | One of `RECEIVED`, `PENDING`, `PROCESSING`, `SUCCEEDED`, `REJECTED`, `FAILED`. The API does **not** validate the value when it reads, so the worker must write only these six |
| `createdAt` | S | API | ISO 8601 UTC. Never change it |
| `updatedAt` | S | API, then worker | ISO 8601 with a time zone. Change it on every write |
| `result` | M | worker | Optional. Shape **[OPEN]** |
| `error` | M | worker | Optional. Shape **[OPEN]** |

The record never contains GPS data, and the worker must not add any.

### 3.2 What the API requires when it reads the item [EXISTING]

If any rule below is broken, the API cannot read the record. It returns `503 INTERNAL_ERROR` to the client,
and keeps doing so for that capture.

- `captureId`, `playerId`, `requestHash`, `status`, `createdAt`, `updatedAt` must be present and of type
  String (`S`).
- `createdAt` and `updatedAt` must parse as ISO 8601 **with** a time zone. Write UTC with a trailing `Z`
  (for example `2026-11-27T03:04:05.123456Z`). Do not rely on comparing these strings with `<` or `>`.
- `result` and `error` must be absent or of type **Map (`M`)**. A String, List or Number is an error.
- Extra attributes (for example the lease and token below) are **ignored** by the API.
- Numbers inside `result` and `error` are converted to a JSON integer when they are whole and to a float
  otherwise.
- `result` and `error` must contain only String, Number, Boolean, Null, List and Map values. **Binary and
  the Set types (`SS`, `NS`, `BS`) are not JSON values.** Based on reading the code, a Set would not be
  converted and the response would fail with `500`. This is not covered by a test.
- A DynamoDB item is limited to 400 KB, so `result` and `error` must stay small. (How the territory is
  stored is **[OPEN]**.)

### 3.3 What a client receives [EXISTING]

`GET /api/v1/captures/{captureId}` returns `captureId`, `status`, `createdAt`, `updatedAt` and:

- `result`, only when `status = SUCCEEDED` **and** `result` is present on the record.
- `error`, only when `status` is `REJECTED` or `FAILED` **and** `error` is present on the record.

The maps are passed to the client as they are. Whatever the team decides for their shape is also the
public API shape, so the map client must be told. A record in `RECEIVED` returns `404` to the client.

### 3.4 Attributes the worker adds [PROPOSAL]

| Attribute | Type | Purpose |
|---|---|---|
| `leaseExpiresAt` | N | Epoch seconds. Until then, one worker owns the capture |
| `attemptToken` | S | A random value (for example a UUID) chosen at each claim. Identifies the current owner |
| `attemptCount` | N | How many times the capture was claimed |

The attribute names are **[OPEN]** for the worker owner. They change the data model in `docs/DATA_MODEL.md`
(one more reason to agree on them). The API does not need them.

## 4. Status transitions and conditional DynamoDB operations

### 4.1 Allowed transitions

| From | To | Done by | Label |
|---|---|---|---|
| (none) | `RECEIVED` | API, when it creates the record | [EXISTING] |
| `RECEIVED` | `PENDING` | API, after the message was sent. Conditional on `status = RECEIVED` | [EXISTING] |
| `RECEIVED` or `PENDING` | `PROCESSING` | worker (claim) | [PROPOSAL] |
| `PROCESSING` with an expired lease | `PROCESSING` | worker (reclaim, same operation) | [PROPOSAL] |
| `PROCESSING` | `SUCCEEDED` or `REJECTED` | the worker that holds the token | [PROPOSAL] |
| any non-final | `FAILED` | worker, or a DLQ handler / sweeper (section 7) | [PROPOSAL] / [OPEN] |
| `SUCCEEDED`, `REJECTED`, `FAILED` | anything | nobody. Final states never change | [PROPOSAL] |

[EXISTING] The API's `PENDING` mark can never overwrite the worker's progress: if the worker claimed first,
the API's condition fails and the API does nothing.

### 4.2 Operations (all are single `UpdateItem` calls)

Common: `Key` is `{"PK": {"S": "CAPTURE#<captureId>"}, "SK": {"S": "META"}}` and
`ExpressionAttributeNames` is `{"#s": "status"}` (because `status` is a reserved word). Timestamps are
ISO strings; epoch values are Numbers.

**A. Claim or reclaim** (read the record first with a consistent read and check `playerId`, section 5):

```
UpdateExpression:    SET #s = :processing, updatedAt = :now, leaseExpiresAt = :lease,
                         attemptToken = :token
                     ADD attemptCount :one
ConditionExpression: #s IN (:received, :pending)
                     OR (#s = :processing
                         AND (attribute_not_exists(leaseExpiresAt) OR leaseExpiresAt < :nowEpoch))
ReturnValues:        ALL_NEW
```

`:lease` is `nowEpoch + L` (L is the lease length, section 6). `:token` is a new random string. A failed
condition (`ConditionalCheckFailedException`) means the capture is final or another worker holds a valid
lease. Re-read the record and decide again (section 5). Never retry the same write blindly.

**B. Extend the lease** (optional, only for long jobs):

```
UpdateExpression:    SET leaseExpiresAt = :lease, updatedAt = :now
ConditionExpression: #s = :processing AND attemptToken = :token
```

**C. Finish with `SUCCEEDED`:**

```
UpdateExpression:    SET #s = :succeeded, result = :result, updatedAt = :now
                     REMOVE leaseExpiresAt
ConditionExpression: #s = :processing AND attemptToken = :token
```

`:result` must be a DynamoDB Map (`{"M": {...}}`) that follows section 3.2.

**D. Finish with `REJECTED`** (a permanent problem with the route):

```
UpdateExpression:    SET #s = :rejected, error = :error, updatedAt = :now
                     REMOVE leaseExpiresAt
ConditionExpression: #s = :processing AND attemptToken = :token
```

**E. Finish with `FAILED` by the worker that holds the token:** the same as D with `:failed`.

**F. Finish with `FAILED` without a token** (a DLQ handler or sweeper, or the attempt limit in section 7):

```
UpdateExpression:    SET #s = :failed, error = :error, updatedAt = :now
                     REMOVE leaseExpiresAt
ConditionExpression: #s IN (:received, :pending, :processing)
```

Status and `result`/`error` are always written **in the same call**. Otherwise a client could see
`SUCCEEDED` before the `result` exists (the API then returns no `result` at all).

## 5. Duplicate delivery and idempotency

[EXISTING] Duplicate messages are expected. The API sends a message before it marks `PENDING`. If the
send worked but the mark failed, the client gets `503` and its retry (same `Idempotency-Key`) sends the
same message again. Standard SQS can also deliver a message twice by itself. The worker can also receive a
message while the record is still `RECEIVED`.

The unit of idempotency is `captureId`. For every delivery the worker reads the record (consistent read)
and acts as follows. [PROPOSAL]

| What the worker finds | Action | Message |
|---|---|---|
| `RECEIVED` or `PENDING` | Claim (operation A), process | Delete after the final write succeeded |
| `PROCESSING`, lease not expired | Do nothing. Another worker is running | **Keep**: report the invocation as failed so SQS delivers it again later |
| `PROCESSING`, lease expired | Reclaim (operation A), process again | Delete after the final write succeeded |
| `SUCCEEDED`, `REJECTED` or `FAILED` | Do nothing | Delete |
| No record for `captureId` | Anomaly: the API creates the record before it sends the message. Process nothing | **Keep** (it ends in the DLQ) |
| `playerId` differs between message and record | Anomaly. Process nothing. Log the IDs only | **Keep** (it ends in the DLQ) |

Because every state change is conditional, two workers that receive the same message at the same time
cannot both claim it: one claim succeeds, the other fails the condition and re-reads.

Processing the same route twice must give the same final record. Whether the calculation is
deterministic depends on the territory logic, so this is **[OPEN]**.

## 6. Processing lease and attempt token (stale-worker protection) [PROPOSAL]

**The problem.** A worker claims a capture and then crashes, times out or stalls. SQS delivers the message
again. Without a lease, the capture stays `PROCESSING` for ever. A worker that only stalled could also wake
up later and overwrite the result of the worker that took over.

**Lease.**

1. A claim sets `leaseExpiresAt = now + L`. While it is in the future, only the holder works on the capture.
2. A later delivery that finds an expired lease reclaims the capture (operation A) with a **new** token.
3. A delivery that finds a valid lease changes nothing and keeps the message.

**Attempt token (stale-worker protection).** Every claim writes a new random `attemptToken`, and every
later write (extend, success, rejected, failed with token) requires the token to match.

- Worker A claims with token A and stalls past the lease.
- Worker B reclaims with token B. The record now holds token B.
- Worker A wakes up and tries to finish. Its condition `attemptToken = A` fails. A writes nothing.
- When A loses ownership it reports its invocation as **failed** and does not delete anything. Reason: its
  message handle may be stale, and a deleted message could be B's only copy. The next delivery finds a final
  record and deletes the message. This costs one harmless extra delivery.

**Choosing the lease length.** With `T` = worker function timeout, `L` = lease length, `V` = queue
visibility timeout: `T < L <= V`. If `L <= T`, a healthy worker can be reclaimed. If `L > V`, a redelivered
message still finds a valid lease and counts toward `maxReceiveCount` for nothing. AWS also advises `V` of at
least 6 times `T` for Lambda event sources. Example only, not a decision: `T` = 60 s, `L` = 120 s,
`V` = 360 s. The real values are **[OPEN]** (section 10).

## 7. Retry and DLQ behavior

### 7.1 Outcomes and message handling [PROPOSAL]

| Situation | Final write | Message |
|---|---|---|
| Success | C (`SUCCEEDED`) | Delete |
| The route fails the plausibility checks (permanent) | D (`REJECTED`) | Delete. Do not retry |
| Temporary error (DynamoDB or an internal error) | None | Keep. SQS retries after `V` |
| Another worker holds a valid lease | None | Keep |
| Ownership lost (a token condition failed) | None | Keep |
| Final state already reached | None | Delete |
| Anomaly (no record, or `playerId` mismatch) | None | Keep |

### 7.2 Unreadable messages [PROPOSAL]

The API never produces these, so this is defensive. If the body is not JSON, `route.encoding` is unknown, the
base64 or gzip is invalid, the route JSON is invalid, or `schemaVersion` is not `1`: if `captureId` and
`playerId` can be read and the record matches, write `FAILED` (operation F) and delete the message.
Otherwise keep the message so it ends in the DLQ. The exact `error` content is **[OPEN]**.

### 7.3 Attempt limit [PROPOSAL]

The claim increases `attemptCount`. Before claiming, if the stored `attemptCount` is already at or above
`MAX_ATTEMPTS`, the worker writes `FAILED` (operation F) and deletes the message instead of processing again.
This ends a capture that keeps crashing the worker. For it to work, `MAX_ATTEMPTS` must be **lower** than the
queue's `maxReceiveCount`, so the worker sees the message before SQS sends it to the DLQ. Both numbers are
**[OPEN]**.

### 7.4 What the DLQ does not do [EXISTING behavior of AWS]

Moving a message to the DLQ does **not** change the DynamoDB record. Neither the API nor the worker updates
it today. A capture whose message reached the DLQ stays `PENDING` or `PROCESSING`, and the client polls it
for ever. With 7.3 in place, the DLQ should receive only messages that never reach the claim step (an
unreadable message, a missing record, a mismatch, or DynamoDB unavailable for the whole retry period).

**How such a record becomes `FAILED` is an open infrastructure/worker decision [OPEN].** This document does
not choose. Options:

| Option | How | Weak point |
|---|---|---|
| A. DLQ handler | A small Lambda reads the DLQ and writes `FAILED` (operation F) | One more function to build and deploy |
| B. Last-attempt write | The worker checks the SQS receive count and writes `FAILED` on the last attempt | Cannot help if the worker cannot start or crashes on that attempt |
| C. Sweeper | A scheduled job marks old non-final records `FAILED` | Needs a way to find them (a scan or an index). The current table has none |
| D. A mix | For example 7.3 plus A as a safety net | More work |

## 8. Queue and Lambda settings that the worker depends on

| Setting | Value | Label |
|---|---|---|
| Batch size | 1 (the lead's preference for the MVP) | [PROPOSAL] |
| Partial batch response | Not needed with batch size 1. If the batch size grows, the function must report failed message ids (`ReportBatchItemFailures`), otherwise one failure retries the whole batch | [PROPOSAL] |
| Worker timeout `T`, lease `L`, visibility timeout `V` | `T < L <= V`, `V` at least `6 * T` | values [OPEN] |
| `maxReceiveCount` and DLQ | A DLQ is recommended. `MAX_ATTEMPTS` below `maxReceiveCount` | values [OPEN] |
| Worker permissions on DynamoDB | `GetItem`, `UpdateItem` on the captures table, plus whatever the territory storage needs | [PROPOSAL] |
| Worker permissions on SQS | Read and delete from the queue (the event source mapping uses the function role) | [PROPOSAL] |
| Logging | Log `captureId`, the transition and `attemptCount`. **Never** log the message body, the route or coordinates | [PROPOSAL] |

## 9. Exact fields the worker persists

For the API to retrieve and show a capture correctly. Never change `PK`, `SK`, `captureId`, `playerId`,
`requestHash` or `createdAt`.

| Event | `status` | `updatedAt` (S, ISO with `Z`) | `result` (M) | `error` (M) | Lease fields (proposal) |
|---|---|---|---|---|---|
| Claim or reclaim | `PROCESSING` | yes | no | no | set `leaseExpiresAt`, `attemptToken`; `attemptCount` +1 |
| Success | `SUCCEEDED` | yes | **yes** (shape [OPEN]) | no | remove `leaseExpiresAt` |
| Rejected | `REJECTED` | yes | no | **yes** (shape [OPEN]) | remove `leaseExpiresAt` |
| Failed | `FAILED` | yes | no | **yes** (shape [OPEN]) | remove `leaseExpiresAt` |

Each row is one conditional `UpdateItem` (section 4.2). `result` and `error` follow section 3.2.

## 10. Pending team decisions [OPEN]

These are **not** decided by the API side. The API stores `result` and `error` as opaque maps and passes
them through.

1. **Final `result` shape** for `SUCCEEDED`: pending team decision. It covers the territory representation
   (polygon format, coordinates, area and its unit), how overlap with other players is resolved, and any
   score or XP.
2. **Final `error` shape and codes** for `REJECTED` and `FAILED`: pending team decision. `INVALID_ROUTE` is
   reserved in the API contract. `docs/GAME_RULES.md` lists other codes (for example
   `CAPTURE_ALREADY_PROCESSED`); they have **not** been reconciled with `docs/API_CONTRACT.md` section 6.
3. **GPS plausibility thresholds** (maximum speed, jump distance, accuracy limit, minimum length, loop
   closing): pending team decision.
4. **Territory rules and territory data model**, and where territories are stored (`docs/DATA_MODEL.md`).
5. **Whether the calculation is deterministic**, so that processing twice gives the same result.
6. **Lease and queue values:** `T`, `L`, `V`, `maxReceiveCount`, `MAX_ATTEMPTS`.
7. **Names of the worker's attributes** (`leaseExpiresAt`, `attemptToken`, `attemptCount`) and whether to
   use the attempt token.
8. **How a record becomes `FAILED` after the DLQ** (section 7.4).
9. **Cleanup of records stuck in `RECEIVED`** (the API sets no TTL).
10. **A way for clients to read territories.** The map design shows other players' areas. That would be a
    new API route, not part of the current MVP.
11. **Hardening in the API** if the team wants it: converting Set values in `result`/`error`, or rejecting
    them. Today the worker must avoid them.

## 11. Suggested worker tests (local fakes, no AWS) [PROPOSAL]

1. A message arrives while the record is `RECEIVED`; the worker claims it.
2. The same message is delivered twice at once; only one claim succeeds.
3. The record is final; the message is deleted and nothing is written.
4. `PROCESSING` with a valid lease; nothing changes and the message is kept.
5. `PROCESSING` with an expired lease; the capture is reclaimed with a new token.
6. A stale worker finishes after a reclaim; its write is refused and nothing is overwritten.
7. A permanent route problem writes `REJECTED` with `error`, and the message is deleted.
8. A temporary DynamoDB error keeps the message and writes nothing.
9. The attempt limit writes `FAILED`.
10. An unreadable message and a missing record.
11. `result` and `error` are written as Maps without Sets or Binary values.
12. The API's `mark_pending` arriving after the claim leaves the status untouched (this already holds in the
    API's own tests).

## 12. Not covered

- Any worker code, territory algorithm or game rule.
- Infrastructure for the worker (`docs/INFRASTRUCTURE_REQUIREMENTS.md` covers the API Lambda only).
- Alarms, dashboards, monitoring of the DLQ and any production security review.