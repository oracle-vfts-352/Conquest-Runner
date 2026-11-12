# Capture record proposal (for the capture API)

> **DRAFT PROPOSAL for the technical lead. Not approved.**
> It does **not** replace `docs/DATA_MODEL.md`, which stays unchanged. It describes the capture
> metadata item that `backend/api/dynamodb_repository.py` reads and writes, starts from the key
> layout in `DATA_MODEL.md` section 3, and lists every place where it differs, so each can be
> accepted or changed. Nothing here has been deployed or tested against a real DynamoDB table.

## 1. Where this follows `DATA_MODEL.md`

- Single table with partition key `PK` and sort key `SK`.
- Capture metadata item: `PK = CAPTURE#<captureId>`, `SK = META`.
- `captureId`, `playerId`, `status`, `createdAt`, `updatedAt` and `requestHash` as in section 5.
- Statuses from the contract, with one internal addition (see 2c).
- Idempotency, recovery and conditional writes as required by sections 7 and 10.
- The route is never stored in the metadata item and no log or response contains it.

## 2. Where it differs (please decide)

| | `DATA_MODEL.md` | This proposal | Why |
|---|---|---|---|
| **a. Route storage** | Section 6: route in DynamoDB as `ROUTE#<n>` chunks; the queue message holds a reference | Route travels inside the SQS message (gzip + base64) | The lead's later decision. **Section 6 and the "SQS message should contain a capture reference" paragraph need updating** |
| **b. Idempotency record** | Separate item `IDEMPOTENCY#<playerId>#<keyHash>` / `REQUEST` | **No separate item.** The capture ID is derived from the player and the key (`capture_` + 32 hex of SHA-256), so a conditional create of the `META` item is the idempotency check, and `requestHash` on it detects a key reused with a different body | One item and one conditional write: no transaction and no way for the two items to disagree. If the team prefers the separate record, `dynamodb_repository.py` is the only code that changes |
| **c. Status values** | `PENDING`, `PROCESSING`, `SUCCEEDED`, `REJECTED`, `FAILED` | Adds `RECEIVED`: stored but not yet queued. Never returned to clients (reads give `404`) | Makes the "record, then queue, then confirm" workflow recoverable (section 7) |
| **d. Result and error** | Flat attributes: `capturedAreaM2`, `totalOwnedAreaM2AfterCapture`, `validationErrorCode`, ... | Two maps: `result` and `error` (`code`, `message`) | The API sends them to the client unchanged, and the contract has an error `message`. The lead and the worker owner should choose. Mapping flat attributes to the contract's `result` / `error` is a small change in the repository |
| **e. Owner check** | Key has no player | Same, plus every read checks `playerId` equals the caller; a capture of someone else is "not found" | A player must never read another player's capture |
| **f. Other attributes** | `routeSampleCount`, `processingAttempt`, `resultVersion`, `completedAt`, `idempotencyKeyHash`, ... | Not written by the API | Worker or later; can be added |

## 3. Capture metadata item

| Attribute | Type | Written by | Notes |
|---|---|---|---|
| `PK` | String | API | `CAPTURE#<captureId>` |
| `SK` | String | API | `META` |
| `captureId` | String | API | `capture_<32 hex>`, derived from the player and the `Idempotency-Key` |
| `playerId` | String | API | The verified JWT `sub` claim, never taken from the request body |
| `requestHash` | String | API | SHA-256 of the submitted route, to detect a key reused with different content (`409`) |
| `status` | String | API, then worker | See section 5 |
| `createdAt` | String | API | ISO 8601 UTC, for example `2026-10-23T01:00:00Z` |
| `updatedAt` | String | API, then worker | ISO 8601 UTC |
| `result` | Map | Worker | When `SUCCEEDED`; the contract shows `capturedAreaM2` and `totalOwnedAreaM2` |
| `error` | Map | Worker | When `REJECTED` or `FAILED`: `code`, `message` |

The exact fields inside `result` and `error` are **not agreed** with the worker owner.
`status` is a DynamoDB reserved word, so updates use an attribute name placeholder (`#s`).

## 4. Access patterns used by the API

| Operation | DynamoDB call | Notes |
|---|---|---|
| Find a capture | `GetItem` with `ConsistentRead` | Consistent, so a retry always sees the item it just created. The caller's `playerId` is then compared |
| Create a capture | `PutItem` with `attribute_not_exists(PK)` | An existing item is never overwritten; the API reuses it |
| Mark as queued | `UpdateItem` with condition `status = RECEIVED` | Sets `PENDING` and `updatedAt`. If the worker has already moved on, the condition fails and its progress is kept |

## 5. Status values

| Status | Visible to the client | Set by | Meaning |
|---|---|---|---|
| `RECEIVED` | No (reads return `404`) | API | Stored, message not yet accepted by the queue |
| `PENDING` | Yes | API | Message accepted by the queue |
| `PROCESSING` | Yes | Worker | Being processed |
| `SUCCEEDED` | Yes | Worker | Ownership changes committed; `result` is set |
| `REJECTED` | Yes | Worker | A game rule failed; `error` is set |
| `FAILED` | Yes | Worker | Processing could not finish; `error` is set |

`RECEIVED` can stay forever if the client never retries after a failure; cleanup is not designed.

## 6. What the worker must do

- Treat the SQS message as at-least-once: a second message for the same `captureId` must not
  change ownership twice or be counted twice (the lead confirmed this requirement).
- Update the same item: `PK = CAPTURE#<captureId>`, `SK = META`.
- Use **conditional updates** for every status change, so a duplicate or late message cannot
  move a capture backwards or apply a result twice.

Suggested transitions (a proposal for the worker owner):

| From | To | Condition | Notes |
|---|---|---|---|
| `RECEIVED` or `PENDING` | `PROCESSING` | `status IN (RECEIVED, PENDING)` | If the condition fails, another run owns it: stop without error |
| `PROCESSING` | `SUCCEEDED`, `REJECTED` or `FAILED` | `status = PROCESSING` | Write `updatedAt` and `result` or `error` in the same update |
| a final status | (nothing) | | A duplicate message for a finished capture is acknowledged and ignored |

**Race:** the API sends the SQS message first and marks the item `PENDING` afterwards, so the
worker can receive the message while the status is still `RECEIVED`. The API's update is
conditional and never overwrites the worker's progress; the worker must accept both `RECEIVED`
and `PENDING` as a start. Numbers in `result` come back from the SDK as `Decimal`; the API
converts them to `int` or `float` when reading.

Ownership changes must be committed in the same all-or-nothing step as the final status or be
safe to repeat (`DATA_MODEL.md` section 10). That is the worker's design, not the API's.

## 7. Open questions

1. Accept the differences in section 2 (a to f)? Which layout for idempotency (2b) and for the
   result and error attributes (2d)?
2. **Finding unfinished captures** (`DATA_MODEL.md` section 13, item 10): an index on `status` and
   `updatedAt` would be needed. Not created here.
3. **Retention:** how long are capture items kept? No TTL attribute is defined.
4. **Cleanup** of stuck `RECEIVED` items.
5. Table name, billing mode and encryption: infrastructure (`infrastructure/template.yaml`).
   The API reads the table name from `CAPTURES_TABLE_NAME` (name proposed, not agreed).
6. The history entry layout (`PLAYER#<id>` / `CAPTURE#<timestamp>#<captureId>`) is not written by
   this API; the worker or a later task would write it.
