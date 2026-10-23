
@'
# ConquestRunner — Game Rules

## 1. Core Principles

- Players capture territory by recording a running route that forms a valid closed loop.
- The backend is the source of truth for route validity, territory ownership, and scores.
- The frontend may detect a candidate loop, but cannot grant territory or determine authoritative scores.
- Rejected captures must not change territory ownership or scores.
- Each geographic area can belong to at most one player at a time.

## 2. Capture Flow

1. The player records GPS samples while running.
2. The frontend submits the route to the authenticated API.
3. The API validates the request and queues the capture for processing.
4. The worker independently validates the route and constructs the capture polygon.
5. The worker calculates the affected territory and applies ownership changes.
6. The capture becomes successful only after the required changes are durably committed.
7. The frontend retrieves the final capture status and refreshes the map and score.

A queued or pending capture is not yet a successful capture.

## 3. Initial Route-Validation Thresholds

These are initial configurable MVP values. They must be tested with synthetic routes and, where practical, real GPS recordings before being treated as final.

| Rule | Initial threshold |
|---|---:|
| Minimum recorded route distance | 200 m |
| Minimum elapsed time | 60 seconds |
| Maximum gap between consecutive GPS samples | 30 seconds |
| Maximum accepted GPS accuracy radius | 50 m |
| Maximum start/end separation | 30 m |
| Minimum capture polygon area | 1,000 m² |
| Maximum sustained plausible running speed | 8 m/s |
| Maximum coordinate samples per submission | 10,000 |

### Validation requirements

- Reject missing, malformed, non-finite, or out-of-range coordinates.
- Validate timestamps and sample ordering.
- Reject routes that do not satisfy the configured loop-closure rule.
- Check route distance, elapsed time, GPS accuracy, sample gaps, and plausible movement speed.
- Reject polygons that are invalid, empty, or below the minimum area.
- Use suitable metric or geodesic calculations for distance and area. Raw latitude/longitude degrees are not metres.
- Handle duplicate samples, suspicious jumps, and insufficient GPS data according to documented validation rules.
- A single speed spike must not automatically prove cheating; evaluate the route and data quality using explicit, tested rules.
- Validate repaired geometry again before using it for ownership changes.

Thresholds and validation outcomes must be configurable or centralized rather than independently hardcoded in different components.

## 4. Territory Ownership Rules

Let `C` be a valid capture polygon.

- **Unclaimed land:** land inside `C` becomes owned by the capturing player.
- **Opponent territory:** territory intersecting `C` transfers to the capturing player within the captured area.
- **Outside the capture:** land outside `C` keeps its previous owner.
- **Existing player territory:** newly captured land that already belongs to the capturer must not be counted twice.
- **Disconnected territory:** valid remaining fragments may be represented as multiple polygons.
- **Invalid geometry:** if the geometry cannot be safely validated or processed, reject or fail the capture without partially applying ownership changes.

Ownership changes must preserve the rule that no geographic area is simultaneously owned by two players.

### Geometry requirements

- Calculate intersections, differences, and unions using an appropriate geographic projection or geodesic approach.
- Support holes and multipolygons where the geometry engine permits them.
- Revalidate results after geometry repair or transformation.
- Use an explicitly defined spatial lookup strategy to identify potentially affected territories. DynamoDB alone does not provide arbitrary polygon-intersection queries.

## 5. Scoring

A player's score is the total net area of territory they currently own.

- Capturing unclaimed land increases the player's score.
- Stealing an opponent's land increases the capturer's score and decreases the previous owner's score.
- Losing territory reduces the previous owner's current score.
- Overlapping a player's own territory must not create duplicate area or points.
- Historical capture records may be retained, but historical captured area is not the current score.
- Rejected captures do not affect scores.
- Score calculations must be based on durable ownership state or a reliably reconciled representation of it.

## 6. Capture State and Idempotency

Each capture must have a stable identifier and a documented lifecycle, such as:

- `PENDING` — accepted for asynchronous processing.
- `PROCESSING` — being validated or calculated.
- `SUCCEEDED` — ownership changes and required capture results are durably committed.
- `REJECTED` — the route or polygon failed a validation rule.
- `FAILED` — processing could not complete successfully.

The exact persisted states and retry policy must be consistent with the API contract.

- Repeating a request with the same idempotency key must not create a second logical capture.
- Duplicate SQS deliveries must not apply ownership changes twice.
- A client that loses its connection must be able to retrieve the existing capture status.
- A worker retry after a crash must determine whether the capture already committed.
- Do not report success before the ownership changes required by the capture are durable.

## 7. Concurrency and Failure Handling

Overlapping captures may be processed close together or concurrently.

- Define a deterministic conflict-resolution rule. For the MVP, the intended rule is that the latest successfully committed capture determines ownership of overlapping land.
- The implementation must prevent lost updates and overlapping final ownership when captures conflict.
- Use appropriate conditional writes, transactions, version checks, serialization, or another documented coordination strategy.
- A single SQS queue does not automatically guarantee correct concurrent updates.
- A worker crash before commit must not leave partial ownership changes.
- A retry after commit must not repeat the ownership changes.
- If ownership updates span multiple durable writes, define how partial failures are prevented, detected, or recovered.
- Leaderboard or derived-score failures must not silently corrupt durable territory state; define reconciliation behavior.

## 8. Abuse Prevention and Privacy

- Derive player identity from trusted authentication context, never from an untrusted client-supplied player ID.
- Apply request rate limits, payload limits, sample-count limits, and appropriate pending-job limits.
- Validate coordinate ranges, timestamps, route distance, speed, sample gaps, and geometry on the server.
- Treat client-side validation as user experience, not a security boundary.
- Avoid logging authentication tokens or unnecessary precise GPS data.
- Do not expose a player's exact private route publicly without an explicit product decision and appropriate consent.

These checks can reduce abuse but cannot conclusively prove that a person physically ran the route.

## 9. Error Categories

Use stable error codes in the API contract. Suggested categories include:

| Error code | Meaning |
|---|---|
| `INVALID_ROUTE` | Malformed or invalid route data |
| `LOOP_NOT_CLOSED` | Route does not meet the loop-closure rule |
| `ROUTE_TOO_SHORT` | Route distance is below the configured minimum |
| `AREA_TOO_SMALL` | Capture polygon area is below the configured minimum |
| `GPS_DATA_INSUFFICIENT` | GPS quality, sample gaps, or timestamps fail validation |
| `CAPTURE_ALREADY_PROCESSED` | Capture identifier or idempotency behavior indicates an existing capture |
| `CAPTURE_PROCESSING_FAILED` | Processing could not complete |

The API contract must define which conditions return an HTTP error immediately and which appear as a final asynchronous capture status. Do not invent separate response formats in individual components.

## 10. Required Tests

### Route validation
- Valid closed loop.
- Loop that is not closed.
- Route shorter than the minimum distance or duration.
- Polygon below the minimum area.
- Invalid coordinates, timestamps, or sample ordering.
- Excessive GPS accuracy radius or sample gap.
- Implausible movement and duplicate samples.
- Too many coordinate samples.
- Invalid polygon, hole, or multipolygon edge cases.

### Ownership and scoring
- Capture entirely unclaimed land.
- Capture part of one opponent's territory.
- Capture all of an opponent's territory.
- Capture territory belonging to multiple opponents.
- Overlap the capturer's own territory.
- Preserve land outside the capture polygon.
- Verify that transferred land is not counted twice.
- Verify that rejected captures do not change ownership or scores.

### Reliability
- Submit the same capture repeatedly.
- Process the same queue message more than once.
- Retry after a worker failure before commit.
- Retry after commit but before message acknowledgement.
- Process overlapping captures concurrently.
- Simulate partial persistence failures and verify recovery.
- Verify capture status and leaderboard consistency after retries.

Use deterministic synthetic GPS routes and geometry fixtures for automated tests. Do not rely only on live GPS recordings or manual map testing.

## 11. MVP Boundaries

Required for the MVP:
- Route recording and closed-loop validation.
- Server-side route and polygon validation.
- Capturing unclaimed land and transferring overlapping opponent territory.
- Current net-area scoring.
- Capture status and basic history.
- Idempotent asynchronous processing.
- Basic abuse prevention and automated tests.

Defer advanced anti-cheat, alliances, seasons, power-ups, territory decay, social feeds, and real-time multiplayer effects until core ownership and scoring are reliable.

## 12. Decisions to Finalize

Before production use, document and test:

1. Final GPS thresholds and their configuration.
2. Exact distance, duration, closure, and speed calculations.
3. The geographic projection or area-calculation method.
4. Geometry repair and rejection behavior.
5. The spatial-index strategy.
6. The concurrency and commit-order strategy.
7. The atomicity and recovery strategy for ownership changes.
8. Capture status transitions, retry rules, and API error mappings.

Keep these rules aligned with `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, and `docs/DATA_MODEL.md`.
'@ | Set-Content -Path .\docs\GAME_RULES.md -Encoding utf8

Write-Host "GAME_RULES.md replaced."
