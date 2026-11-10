# ConquestRunner — Data Model

> **DRAFT PROPOSAL. Not approved by the technical lead.**
> Written from the code in `backend/api/dynamodb_repository.py`, which is the source of truth.
> Nothing here has been deployed or tested against a real DynamoDB table.

This document covers only the **capture record** used by the capture API. Player profiles,
leaderboard data and capture history are not designed yet (see *Open questions*).

## Capture record

One item per capture. The record never contains GPS data. The route is **not** stored in
DynamoDB: it travels inside the SQS message, compressed with gzip and encoded with base64
(lead's MVP decision, see `docs/API_CONTRACT_CHANGES.md`).

| Attribute | Type | Written by | Notes |
|---|---|---|---|
| `pk` | String | API | Partition key: `PLAYER#<playerId>` |
| `sk` | String | API | Sort key: `CAPTURE#<captureId>` |
| `captureId` | String | API | `capture_<32 hex>`, derived from the player and the `Idempotency-Key` |
| `playerId` | String | API | The verified JWT `sub` claim, never taken from the request body |
| `requestHash` | String | API | SHA-256 of the submitted route. Used to detect a key reused with different content (`409`) |
| `status` | String | API, then worker | See *Status values* |
| `createdAt` | String | API | ISO 8601 UTC, for example `2026-10-23T01:00:00Z` |
| `updatedAt` | String | API, then worker | ISO 8601 UTC |
| `result` | Map | Worker | Set when `SUCCEEDED`, for example `capturedAreaM2`, `totalOwnedAreaM2` |
| `error` | Map | Worker | Set when `REJECTED` or `FAILED`: `code`, `message` |

The exact fields inside `result` and `error` are **not agreed** with the worker owner yet.
The API sends them to the client unchanged, so they must be JSON-friendly.

## Key design

- The player ID is part of the partition key. A read always names the caller's own player ID,
  so a player cannot read another player's capture even by guessing a capture ID.
- Because the capture ID is derived from the player and the `Idempotency-Key`, a retry
  finds the same item.
- A table name is **not** fixed here. The API reads it from the environment variable
  `CAPTURES_TABLE_NAME` (name proposed, not agreed).

## Access patterns used by the API

| Operation | DynamoDB call | Notes |
|---|---|---|
| Find a capture | `GetItem` with `ConsistentRead` | Consistent read so a retry always sees the record it just created |
| Create a capture | `PutItem` with `attribute_not_exists(pk)` | If the item exists nothing is overwritten and the API reuses it |
| Mark as queued | `UpdateItem` with condition `status = RECEIVED` | Sets `PENDING` and `updatedAt`. If the worker has already moved on, the condition fails and the worker's progress is kept |

`status` is a DynamoDB reserved word, so updates use an attribute name placeholder (`#s`).

## Status values

| Status | Visible to the client | Set by | Meaning |
|---|---|---|---|
| `RECEIVED` | No (reads return `404`) | API | Record stored, message not yet sent to the queue |
| `PENDING` | Yes | API | Message accepted by the queue |
| `PROCESSING` | Yes | Worker | Being processed |
| `SUCCEEDED` | Yes | Worker | Ownership changes committed. `result` is set |
| `REJECTED` | Yes | Worker | Route broke a game rule. `error` is set |
| `FAILED` | Yes | Worker | Processing could not finish. `error` is set |

`RECEIVED` can stay forever if the client never retries after a failure. Cleanup is not designed yet.

## What the worker must do

- Treat the SQS message as at-least-once: a second message for the same `captureId` must not
  change ownership twice or be counted twice.
- Update the same item (`pk`, `sk` from the message's `playerId` and `captureId`).
- Use **conditional updates** for every status change, so a duplicate or late message cannot
  move a capture backwards or apply a result twice.

Suggested transitions (a proposal for the worker owner to review):

| From | To | Condition expression | Notes |
|---|---|---|---|
| `RECEIVED` or `PENDING` | `PROCESSING` | `status IN (RECEIVED, PENDING)` | See the race below. If the condition fails, another worker run owns it: stop without error |
| `PROCESSING` | `SUCCEEDED`, `REJECTED` or `FAILED` | `status = PROCESSING` | Write `updatedAt` and `result` or `error` in the same update |
| `SUCCEEDED`, `REJECTED`, `FAILED` | (nothing) | | A duplicate message for a finished capture is acknowledged and ignored |

**Race to be aware of:** the API sends the SQS message first and marks the record `PENDING`
afterwards. The worker can therefore receive the message while the record is still `RECEIVED`.
The API's `RECEIVED -> PENDING` update is conditional, so it never overwrites the worker's
progress, and the worker must accept both `RECEIVED` and `PENDING` as a starting state.

Ownership changes (the territory itself) must be committed in the same all-or-nothing step as
the final status, or be safe to repeat. The API cannot guarantee this: it is the worker's design.
- Numbers inside `result` are returned as `Decimal` by the AWS SDK. The API converts them to
  `int` or `float` when reading.

## Open questions

1. **History and leaderboard:** the current key supports "get one capture". Listing a player's
   captures is possible with a query on `pk`, but a leaderboard needs another design (a separate
   item type or an index). Is it in scope?
2. **Retention:** how long are capture records kept? A TTL attribute is not defined.
3. **Cleanup of stuck `RECEIVED` records** (client never retried).
4. **Item size:** records are small (no route), but `result` and `error` should stay small.
   The route lives only in the SQS message (and the dead-letter queue if processing keeps failing),
   so its retention is the queue's retention, not the table's.
5. **Table name, billing mode (on-demand or provisioned) and encryption settings:** owned by the
   infrastructure (`infrastructure/template.yaml`).
6. **Exact shape of `result` and `error`,** and how the worker updates the item idempotently.
7. **Player data:** where the player's total owned area and display name live.
