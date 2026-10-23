
@'
# ConquestRunner — Data Model

## 1. Purpose

This document defines the proposed persistence model for the ConquestRunner MVP.

The initial persistence target is Amazon DynamoDB. The model must support:

- Authenticated players.
- Capture submission, status, and results.
- Idempotent request handling.
- GPS route retrieval during processing.
- Current territory ownership and net-area scoring.
- Capture history and basic leaderboard queries.
- Safe retries and recovery after worker failures.

This is a logical starting design, not a finalized production schema. Validate item sizes, query patterns, transaction boundaries, and spatial indexing before deployment.

## 2. Design Principles

- Durable backend state is authoritative.
- Store only the data required for gameplay, processing, and agreed retention periods.
- Keep large route payloads separate from capture metadata.
- Store enough state to recognize duplicate submissions and worker retries.
- Treat leaderboard values as derived data that can be reconciled against authoritative ownership.
- Do not assume DynamoDB can query arbitrary polygon intersections.
- Do not assume multiple independent writes are atomic.
- Never expose private route samples through public player or leaderboard endpoints.

## 3. Proposed Single-Table Layout

The initial proposal uses one DynamoDB table with a partition key `PK` and sort key `SK`.

| Entity | PK | SK | Purpose |
|---|---|---|---|
| Player profile | `PLAYER#<playerId>` | `PROFILE` | Display name and player metadata |
| Capture metadata | `CAPTURE#<captureId>` | `META` | Status, owner, timestamps, result |
| Route chunk | `CAPTURE#<captureId>` | `ROUTE#<chunkNumber>` | Bounded portion of submitted GPS samples |
| Idempotency record | `IDEMPOTENCY#<playerId>#<keyHash>` | `REQUEST` | Maps a retry key to the existing logical capture |
| Capture history entry | `PLAYER#<playerId>` | `CAPTURE#<timestamp>#<captureId>` | Player's capture history |
| Territory fragment | `TERRITORY#<fragmentId>` | `STATE` | Current geometry and owner |
| Spatial index entry | `CELL#<cellId>` | `FRAGMENT#<fragmentId>` | Candidate territory lookup by spatial cell |

These key patterns are illustrative. The final design must define attribute names, indexes, item sizes, consistency needs, and exact access patterns before implementation.

Do not copy these keys into application code independently before the schema is agreed upon.

## 4. Player Profile

A player profile may contain:

- `playerId`
- `displayName`
- `createdAt`
- `totalOwnedAreaM2`
- `profileVersion`
- Optional public profile fields approved by the team

The player ID must be derived from trusted authentication claims.

`totalOwnedAreaM2` is a derived score. It must not become an independent source of truth that can silently disagree with territory ownership.

Define how score updates are committed or reconciled when ownership changes.

## 5. Capture Metadata

Each logical capture has one durable metadata record.

Suggested fields:

- `captureId`
- `playerId`
- `status`
- `createdAt`
- `updatedAt`
- `idempotencyKeyHash`
- `requestHash`
- `routeSampleCount`
- `processingAttempt`
- `validationErrorCode`
- `capturedAreaM2`
- `totalOwnedAreaM2AfterCapture`
- `resultVersion`
- `completedAt`

Fields may be absent when they do not apply to the current status.

### Status values

Use the statuses defined in `docs/API_CONTRACT.md`:

- `PENDING`
- `PROCESSING`
- `SUCCEEDED`
- `REJECTED`
- `FAILED`

Define valid state transitions and retry behavior in the worker implementation.

A capture must not be marked `SUCCEEDED` until the required ownership changes and result are durably committed.

## 6. GPS Route Storage

A capture route may contain up to 10,000 GPS samples.

Do not store all samples in a single DynamoDB item. Store bounded chunks under the capture partition, for example:

- `ROUTE#0000`
- `ROUTE#0001`
- `ROUTE#0002`

Each chunk contains an ordered, bounded range of samples. Keep each item below DynamoDB's item-size limit with sufficient safety margin.

A sample contains the fields required by the API contract:

- `latitude`
- `longitude`
- `timestamp`
- `accuracyMeters`

### Route storage requirements

- Define the chunk size and enforce it in code.
- Preserve original sample ordering.
- Validate the total sample count before accepting a capture.
- Avoid logging full route contents.
- Restrict route access to authorized processing and the relevant player, where route access is exposed.
- Define retention and deletion rules for route samples.
- Do not return route chunks from the ordinary capture-status endpoint.

The API should persist enough request data for safe processing and recovery before confirming acceptance.

The SQS message should contain a capture reference and the minimum required metadata, not the entire GPS route. The worker retrieves the persisted route using the capture reference.

If the team later chooses object storage instead, document the object lifecycle, permissions, encryption, cleanup, and cost implications before changing the model.

## 7. Idempotency Records

An idempotency record maps a player's request key to one logical capture.

Suggested fields:

- `playerId`
- `idempotencyKeyHash`
- `requestHash`
- `captureId`
- `createdAt`
- `expiresAt`, if a retention policy is adopted

Requirements:

- Scope keys to the authenticated player.
- Hash keys where appropriate instead of storing raw values unnecessarily.
- Repeating the same key and same logical request returns or references the existing capture.
- Reusing the same key with different request content returns an idempotency conflict.
- Use conditional writes to prevent concurrent requests from claiming the same key.
- Define what happens if capture records expire before idempotency records or vice versa.
- Do not rely on TTL deletion happening immediately.

The idempotency record, capture metadata, route storage, and SQS submission must work together as a recoverable submission workflow. DynamoDB and SQS do not share a single atomic transaction.

## 8. Territory Ownership

Represent current owned land as territory fragments. A fragment is a valid geographic polygon or multipolygon with one current owner.

Suggested fields:

- `fragmentId`
- `ownerPlayerId`
- `geometry`
- `geometryVersion`
- `areaM2`
- `updatedAt`
- `lastCaptureId`

The geometry encoding must be explicitly selected and consistently interpreted by the geometry engine.

A territory fragment must have one owner. When a capture transfers part of a fragment, the worker may need to produce a transferred fragment and one or more remaining fragments.

The implementation must handle:

- Partial territory overlap.
- Fully consumed fragments.
- Multiple affected owners.
- Disconnected remaining fragments.
- Polygon holes and multipolygons.
- Geometry repair and revalidation.
- Duplicate processing and stale geometry versions.

Do not store a single ever-growing polygon per player without considering item size, geometry complexity, and update contention.

## 9. Spatial Index

DynamoDB does not natively support arbitrary polygon-intersection queries.

The proposed `CELL#<cellId>` index is a logical placeholder for a spatial index, such as H3 cells at an agreed resolution.

The worker can use the spatial index to find candidate fragments, then use the geometry engine to calculate the actual intersections. A shared cell only identifies candidates; it does not prove that two polygons overlap.

Before implementing this index, decide:

- The geographic scope of the MVP.
- The spatial cell system and resolution.
- How polygons covering multiple cells are indexed.
- How very large polygons and cell-boundary cases are handled.
- How stale index entries are detected and repaired.
- How index changes remain consistent with ownership changes.

The spatial index is an acceleration structure, not the authoritative owner record.

## 10. Ownership Updates and Concurrency

A capture can modify several territory fragments and several player scores. Those updates must not silently produce lost ownership or double-counted land.

The schema alone does not solve this problem.

Before implementation, define a commit strategy that covers:

1. Identifying candidate fragments.
2. Reading their geometry and version.
3. Calculating new ownership geometry.
4. Preventing conflicting captures from committing against stale state.
5. Persisting ownership changes and capture completion.
6. Recovering from interrupted or partially completed work.
7. Reconciling derived scores and spatial-index entries.

Possible techniques include conditional writes, optimistic version checks, DynamoDB transactions for suitably bounded changes, or a durable coordination/commit protocol.

DynamoDB transactions have finite item and request-size limits. Do not assume one transaction can update an unlimited number of fragments.

For the MVP, constrain the supported geographic scope and capture complexity if necessary. Document what happens when one capture exceeds the supported transaction boundary.

The intended game rule is that the latest successfully committed capture determines ownership of overlapping land. The implementation must make this rule precise and test concurrent captures.

## 11. Capture History

A player history entry should support retrieving recent captures without scanning the entire table.

Suggested fields:

- `captureId`
- `createdAt`
- `status`
- `capturedAreaM2`
- `resultCode`, if rejected
- `completedAt`

Use a deterministic sort-key format so entries can be ordered and paginated.

Capture history is historical information. It must not be used as a substitute for current territory ownership or current-area scoring.

Define whether history entries are written synchronously with the final result or reconstructed from authoritative capture records.

## 12. Leaderboard

The MVP leaderboard displays each player's current net owned area.

A possible approach is a dedicated leaderboard index or a queryable score projection. The exact design depends on the expected player count and update frequency.

Requirements:

- Define a stable ordering and tie-breaking rule.
- Never allow clients to write their own scores.
- Update or reconcile derived scores when land is captured or stolen.
- Ensure rejected captures do not affect scores.
- Define how leaderboard reads behave while a capture is pending or being committed.
- Provide a recovery or rebuild process if the projection becomes inconsistent.

Do not assume a DynamoDB scan is an acceptable production leaderboard query.

## 13. Query Access Patterns

The final schema must explicitly support these operations:

1. Get a player profile.
2. Get a capture by `captureId`.
3. Retrieve all route chunks for a capture in sample order.
4. Find or conditionally create an idempotency record.
5. Retrieve recent captures for a player.
6. Find territory fragments that may intersect a capture polygon.
7. Read and conditionally update territory fragments.
8. Calculate or reconcile a player's current owned area.
9. Query the leaderboard in score order.
10. Find unfinished captures for recovery and monitoring.

For each operation, document the table or index used, expected result size, pagination behavior, and consistency requirement.

Avoid table scans for normal user-facing operations.

## 14. Privacy and Retention

- Keep route samples private by default.
- Restrict table and index permissions to the minimum required.
- Never log access tokens or full route payloads.
- Define retention for raw GPS samples, capture metadata, idempotency records, and historical events.
- Define how account deletion or a privacy request affects profile data, route samples, and capture history.
- Avoid exposing internal partition keys or private route data through public API responses.

Retention and deletion rules must be compatible with the ability to audit and reconcile territory ownership.

## 15. Required Tests

### Persistence
- Create and retrieve a capture.
- Retrieve route chunks in the correct order.
- Handle the maximum configured sample count without oversized items.
- Enforce idempotency with conditional writes.
- Reject reuse of a key with different request content.
- Paginate player capture history.

### Ownership
- Capture unclaimed land.
- Transfer part or all of a territory fragment.
- Split a fragment into multiple remaining pieces.
- Preserve single-owner invariants.
- Verify current net-area totals after transfers.
- Verify spatial-index entries match the committed geometry.

### Reliability and concurrency
- Deliver the same SQS message multiple times.
- Retry after failure before commit.
- Retry after commit but before message acknowledgement.
- Submit the same idempotency key concurrently.
- Process overlapping captures concurrently.
- Simulate transaction-limit or conditional-write failures.
- Reconcile score and spatial-index projections after interrupted updates.

Use deterministic test fixtures and verify both geometry and persisted state.

## 16. Decisions to Finalize

Before the data model is considered implementation-ready, agree on:

1. Exact DynamoDB attribute names and types.
2. Required GSIs and their key definitions.
3. Route chunk size and request-persistence workflow.
4. Idempotency retention and conditional-write behavior.
5. Territory geometry encoding and maximum supported complexity.
6. Spatial index, cell resolution, and repair process.
7. Ownership commit and conflict-resolution strategy.
8. Score and leaderboard consistency model.
9. Recovery, reconciliation, retention, and deletion procedures.

Keep this document aligned with `docs/ARCHITECTURE.md`, `docs/GAME_RULES.md`, and `docs/API_CONTRACT.md`.
'@ | Set-Content -Path .\docs\DATA_MODEL.md -Encoding utf8

Write-Host "DATA_MODEL.md created."
