Territory Run — Game Rules & Acceptance Criteria

Document: docs/GAME_RULES.md
Version: 1.0 — Initial Draft
Status: Proposed MVP specification
Project type: GPS-based territory-conquest running game
Primary rule: The latest accepted capture takes ownership of the overlapping territory.

1. Purpose

Territory Run is a gamified running application where players capture geographic territory by running a valid closed loop.

Players can:

Record a GPS running route.

Close a loop to create a capture attempt.

Claim previously unowned land.

Steal land from other players by overlapping their existing territory.

View their current territory, running statistics, and capture history.

Compete on leaderboards based on territory ownership.

The backend is the single source of truth for route validity, territory geometry, ownership, and scoring. The frontend displays results but cannot grant territory independently.

2. Core Game Principles

Server authority: Only the backend can accept a capture and change territory ownership.

Latest accepted capture wins: A valid capture replaces previous ownership in the area it covers.

Fairness: Invalid, duplicate, incomplete, or suspicious routes must not grant territory.

Geometric correctness: Territory must not be counted twice across different players.

Consistency: A capture must not leave ownership partially updated.

Idempotency: Processing the same capture more than once must not grant duplicate rewards.

Transparency: Players should be able to see whether a capture succeeded and why it was rejected.

Privacy: Exact GPS routes must not be publicly exposed without explicit product requirements and appropriate consent.

3. Definitions

Term

Definition

Player

An authenticated user who can submit runs.

GPS route

An ordered sequence of recorded geographic coordinates.

Closed loop

A route whose endpoint is sufficiently close to its starting point to form a polygon.

Capture attempt

A submitted route awaiting backend validation and processing.

Capture polygon

The valid geographic area enclosed by the accepted route.

Territory

An area currently owned by one player.

Overlap

The geographic intersection between a capture polygon and existing territory.

Net area gained

The area that becomes newly owned by a player after subtracting their existing territory.

Capture event

A persistent record of an accepted or rejected capture attempt.

4. Gameplay Rules

4.1 Recording a run

The player signs in.

The player grants location permission.

The frontend records GPS coordinates and timestamps while the run is active.

The frontend displays the route on the map.

The player finishes the run or the application detects a candidate closed loop.

The frontend submits the route to the backend.

The backend validates the route and determines whether a capture is permitted.

If valid, the territory worker calculates the resulting ownership changes.

The player receives the final result after processing succeeds or fails.

The frontend may detect a potential loop for a better user experience, but its decision is never authoritative.

4.2 Closed-loop requirements

A route must meet all of the following requirements:

Contain enough valid GPS samples.

Have valid latitude and longitude values.

Have timestamps in a valid sequence.

Meet the minimum route distance and duration.

Return sufficiently close to the starting point.

Produce a valid polygon with a positive area.

Meet the minimum capture-area threshold.

Pass the route plausibility checks.

The backend must construct and validate the polygon independently. It must not trust a polygon supplied by the frontend as proof of a valid capture.

Initial configurable thresholds for the MVP:

Rule

Initial value

Minimum recorded route distance

200 m

Minimum elapsed time

60 seconds

Maximum gap between consecutive GPS samples

30 seconds

Maximum accepted GPS accuracy radius

50 m

Maximum start/end separation

30 m

Minimum polygon area

1,000 m²

Maximum sustained plausible running speed

8 m/s

Maximum coordinate samples per submission

10,000

These are starting values for testing, not universal definitions of a valid run. The team should calibrate them with real GPS recordings before release. Thresholds should be centrally configured, documented, and covered by tests rather than duplicated across frontend and backend code.

A single implausible speed spike should trigger sample inspection or filtering, not automatically prove cheating. A route with large gaps or insufficient reliable data may be rejected.

4.3 Territory capture and stealing

For a valid capture polygon (C):

Unowned portions inside (C) become owned by the capturing player.

Portions owned by other players inside (C) transfer to the capturing player.

Portions of existing territories outside (C) remain unchanged.

The capturing player retains their own existing territory.

Territory outside (C) is never affected by the capture.

Conceptually, for an existing territory (T_i) belonging to another player:

[
T_i' = T_i \setminus C
]

For the capturing player, whose previous territory is (T_p):

[
T_p' = T_p \cup C
]

The implementation must also account for unowned land and any other territories in the affected region.

Important: The equations describe the logical result, not necessarily the physical DynamoDB storage layout. The worker must implement the equivalent result without double-counting or losing concurrent updates.

4.4 Area and score calculation

The leaderboard ranks players by their current net owned territory area.

Area is measured in square metres.

Polygon operations must use an appropriate metric projection or a geodesic-area calculation. Raw latitude/longitude degrees must not be treated as square metres.

Each geographic point can belong to at most one player at a time.

The same area cannot be counted twice for a single player.

Recapturing territory already owned by the same player does not award additional area for that land.

A successful capture that steals land reduces the previous owner's current territory area.

Historical capture events remain available even if territory is subsequently stolen.

For the MVP:

Current score = total area of all territory currently owned by the player.

Do not use cumulative historical capture area as the primary leaderboard score, because repeated recaptures could inflate scores without increasing current ownership.

The leaderboard should update after the territory transaction has been successfully committed.

4.5 Invalid and rejected captures

A capture must be rejected if any required validation fails, including:

The player is not authenticated.

The route is malformed or exceeds request limits.

Coordinates are invalid or out of range.

The route is too short or does not close sufficiently.

The polygon is empty, invalid, or below the minimum area.

The route contains impossible or suspicious movement that fails the configured policy.

The submission is a duplicate that has already been processed.

The backend cannot establish a safe and consistent territory update.

Rejected captures must not change territory ownership or the player's score.

The system should return a stable error code and a player-readable explanation, without exposing sensitive internal details.

Example error categories:

Code

Meaning

INVALID_ROUTE

Route data is malformed.

LOOP_NOT_CLOSED

Route does not satisfy the closure rule.

ROUTE_TOO_SHORT

Minimum distance or duration was not met.

AREA_TOO_SMALL

Enclosed polygon is too small.

GPS_DATA_INSUFFICIENT

GPS samples are too inaccurate or incomplete.

CAPTURE_ALREADY_PROCESSED

Submission has already been handled.

CAPTURE_PROCESSING_FAILED

Processing failed without committing ownership changes.

The API contract should define the final status codes and response shapes.

5. Fairness and Anti-Abuse Rules

5.1 Server-authoritative processing

The client may submit route coordinates, timestamps, and a unique capture request ID. The server must derive the capture polygon and determine the result.

The client must never be allowed to submit a trusted final area, score, or ownership assignment.

5.2 GPS plausibility

The backend should check:

Coordinate ranges and timestamp ordering.

Unrealistic distances between samples.

Implausible sustained speeds and acceleration.

Large missing-data gaps.

Excessive duplicate or repeated samples.

Invalid or self-intersecting capture geometry.

Repeated suspicious submissions.

These checks reduce abuse but cannot guarantee that every GPS-spoofed route will be detected.

5.3 Request limits

The API should enforce:

Authentication.

Request-size and coordinate-count limits.

Per-user rate limits.

Reasonable limits on simultaneous pending captures.

Idempotency for retries.

Appropriate limits on capture-processing workload.

Rate-limited or oversized requests must not create territory.

5.4 No partial capture

If a capture intersects multiple owners, the system must not transfer only some of the affected territory and then report a successful full capture.

The territory update must either commit completely or leave the previous ownership state intact.

5.5 Fair treatment of failures

If a worker crashes, an SQS message is delivered again, or a client retries after a timeout, the same capture must not award duplicate area or produce contradictory ownership.

A processing failure must not be presented as a successful capture until the durable state is confirmed.

6. Concurrency and Processing Rules

Territory Run uses asynchronous processing, so multiple capture attempts may be processed at the same time.

The team must implement the following rules:

Every capture attempt has a unique ID.

SQS delivery is treated as at least once, not exactly once.

Duplicate messages must be safe to process.

Ownership changes must be serialized or protected by optimistic concurrency control for the affected geographic region.

A worker must read the latest committed ownership state before applying geometry changes.

Conflicting updates must be retried safely or rejected for later processing.

The capture result, ownership changes, area totals, and idempotency state must remain consistent.

A capture must not be marked complete before its required state changes are durable.

If two players submit overlapping captures simultaneously, the backend must apply a deterministic ordering based on successful commit order. The capture that commits later becomes the final owner of the overlapping area.

A DynamoDB single-table design alone does not guarantee atomicity across arbitrary geographic polygons. The implementation must explicitly handle transactions, conditional writes, version checks, affected-region coordination, and DynamoDB transaction limits.

For the MVP, use a documented strategy for coordinating updates to the same geographic region. Do not assume that a single Lambda invocation or SQS queue automatically prevents all race conditions.

7. Territory Geometry Requirements

The geometry engine must:

Validate polygons before processing.

Handle holes, multipolygons, and disconnected territory fragments.

Subtract captured areas from previous owners.

Union the capture area with the new owner's territory.

Avoid double-counting overlapping territory.

Preserve unaffected geometry.

Reject empty or unusable results.

Calculate area using suitable geographic measurements.

Use a spatial lookup strategy so the worker does not need to compare every capture with every territory in the entire game.

The team should define a spatial indexing or geographic partitioning strategy before large-scale testing.

If geometric repair is attempted on an invalid polygon, the repaired result must be validated again. A repair must not silently produce an unintended capture area.

8. Edge Cases and Expected Outcomes

Scenario

Expected result

Route never closes

Reject; no ownership changes.

Loop encloses less than the minimum area

Reject; no ownership changes.

Route contains invalid coordinates

Reject the submission.

Route contains a long GPS gap

Reject or request a new recording according to the configured policy.

Capture covers only unowned land

Assign the captured land to the player.

Capture overlaps one opponent

Transfer the overlapping area to the capturing player.

Capture overlaps several opponents

Transfer each overlapping portion; preserve all unaffected portions.

Capture overlaps the player's own territory

Merge the areas; award no duplicate score.

Capture encloses an existing territory completely

Transfer the enclosed territory to the capturer, subject to the same capture rules.

Two captures overlap in time

Resolve conflicts using the documented commit-order policy.

SQS delivers the same event twice

Apply ownership changes at most once.

Worker crashes before commit

No partial ownership update; retry safely.

Worker crashes after commit but before acknowledgement

Retry must detect prior completion and avoid reapplying the capture.

User loses network after submission

Client can retrieve the existing request's status without creating a second capture.

User signs out before processing completes

Processing remains tied to the authenticated request; no identity substitution.

Capture geometry becomes empty after validation or repair

Reject without modifying territory.

Leaderboard update fails after capture commit

Reconcile or recompute the leaderboard from durable ownership state.

User submits an extremely large route

Reject at request validation or enforce documented limits.

9. Acceptance Criteria

These criteria should become automated tests wherever possible.

A. Route validation

A valid closed-loop route passes validation when all configured thresholds are satisfied.

An open route is rejected.

An invalid coordinate is rejected.

A route below the minimum distance is rejected.

A route below the minimum elapsed time is rejected.

A polygon below the minimum area is rejected.

A route exceeding the coordinate limit is rejected safely.

A route with implausible movement is handled according to the configured validation policy.

The backend independently calculates the polygon and area.

B. Ownership and scoring

Unowned land enclosed by a valid capture becomes owned by the capturer.

Overlapping land is removed from the previous owner's territory.

Land outside the capture polygon remains unchanged.

The capturing player's existing territory is merged without duplication.

Current territory totals match the geometry after a capture.

The leaderboard reflects current ownership rather than cumulative captured area.

Historical capture records remain available after territory is stolen.

Ownership results are deterministic for the same committed input state and processing order.

C. Idempotency and reliability

Reprocessing a completed capture does not change ownership or scores again.

Retrying a request with the same idempotency key returns or references the existing capture.

A failed capture does not leave partial ownership changes.

A worker crash before commit is recoverable.

A worker crash after commit does not duplicate the capture.

Concurrent overlapping captures cannot create overlapping final ownership or lost updates.

Conflicting writes are retried safely or return a documented failure state.

D. Security and fairness

Unauthenticated capture requests are rejected.

Client-provided scores and ownership claims are ignored.

Invalid and oversized requests do not create territory.

Per-user request limits are enforced.

Exact private GPS routes are not exposed through public profile or leaderboard responses.

Logs do not unnecessarily expose sensitive GPS data or authentication tokens.

E. User experience

The player can distinguish pending, successful, and rejected captures.

Rejection responses provide a stable error code and understandable explanation.

A network retry does not create duplicate captures.

The map and statistics refresh after the backend confirms a successful capture.

A pending capture is not shown as final ownership before the backend confirms it.

10. Testing Strategy

Unit tests

Test route validation, closure detection, geometry repair, polygon union and difference, area calculation, score calculation, and idempotency logic independently.

Integration tests

Test the API, queue, worker, and persistence flow, including duplicate SQS messages, failed writes, retries, and concurrent captures.

Geometry fixtures

Create small deterministic fixtures with known expected outcomes:

One capture on unowned land.

One capture that partially overlaps an opponent.

One capture that fully covers an opponent's territory.

One capture overlapping multiple owners.

One capture partially overlapping the player's own territory.

Two concurrent captures covering the same area.

Invalid polygons and polygons with holes.

Repeated processing of the same capture.

Each fixture should assert both the resulting geometry and the area totals.

End-to-end tests

Simulate a player signing in, submitting a route, waiting for processing, and viewing the updated map and leaderboard.

Use synthetic routes and test fixtures rather than relying on real outdoor GPS recordings for deterministic automated tests.

11. MVP Scope

Required for the first playable version

Authentication.

GPS route recording.

Closed-loop capture attempts.

Backend route validation.

Polygon creation and area calculation.

Unclaimed territory capture.

Stealing overlapping territory.

Current territory and area totals.

Basic leaderboard.

Capture status and history.

Idempotent asynchronous processing.

Basic anti-abuse checks.

Automated tests for geometry and ownership.

Deferred until the core game is stable

Alliances and teams.

Seasonal rankings.

Territory decay.

Power-ups and special capture abilities.

Advanced anti-cheat detection.

Notifications for territory theft.

Social feeds.

Real-time multiplayer animations.

Large-scale spatial partitioning optimizations beyond the initial requirements.

These features must not delay correctness of the core capture engine.

12. Rules for Future Changes

Any change to capture behavior must update this document.

Threshold changes must update configuration and relevant tests.

API behavior changes must update docs/API_CONTRACT.md.

Ownership or persistence changes must update docs/DATA_MODEL.md.

Geometry changes must include regression tests.

Contributors must not independently invent different game rules in frontend and backend code.

13. Definition of Done

A feature is complete only when:

The implementation follows this specification.

Validation and failure cases are handled.

Unit tests pass.

Relevant integration tests pass.

Duplicate and retry behavior is safe.

The code passes the repository's CI checks.

The API and data model documentation are updated when necessary.

A reviewer can verify the behavior from the code and tests.

Core acceptance principle: A capture is successful only when the backend has validated the route and durably committed the correct ownership changes. Visual feedback alone is never proof of a successful capture.