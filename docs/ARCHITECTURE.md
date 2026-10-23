
@'
# ConquestRunner — Architecture

## 1. Project Overview

ConquestRunner is a GPS-based running game in which players capture geographic territory by completing closed-loop running routes.

The MVP focuses on route recording, server-validated captures, territory ownership, current-area scoring, and a basic leaderboard.

**Core principle:** the backend is the source of truth for route validation, territory ownership, and scores. The frontend must never grant territory independently.

## 2. Intended Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript, Vite | UI, map interaction, GPS tracking |
| Styling | Tailwind CSS, subject to current project setup | Shared visual design |
| Frontend tests | Vitest, React Testing Library | Component and logic tests |
| Authentication | Amazon Cognito | User authentication and JWTs |
| HTTP API | Amazon API Gateway | HTTPS endpoints and JWT authorization |
| API handler | AWS Lambda, Python | Authenticate context, validate requests, enqueue jobs |
| Queue | Amazon SQS | Asynchronous capture processing |
| Territory worker | AWS Lambda, Python, Shapely | Validate geometry and calculate ownership changes |
| Persistence | Amazon DynamoDB | Capture status, territory state, and player data |
| Infrastructure | AWS SAM / CloudFormation | Infrastructure as code |
| CI | GitHub Actions | Automated checks |

The map provider is not yet selected. Review pricing, usage limits, licensing, and attribution requirements before choosing one.

AWS deployment is not required for initial local development. Do not deploy resources or incur cloud costs without team approval.

## 3. System Flow

1. A player signs in and records a GPS route in the frontend.
2. The frontend submits route samples to the authenticated API.
3. The API validates the request and obtains the player identity from trusted authorizer claims.
4. The API creates or identifies a capture request and submits a job to SQS.
5. A worker validates the route and independently constructs the capture polygon.
6. The worker finds potentially affected territories, calculates geometry changes, and persists a consistent result.
7. The frontend retrieves or receives the capture status and refreshes the map and player statistics.

The API should return `202 Accepted` only after the queue has confirmed successful submission. A queued capture is pending, not yet successful.

## 4. Component Boundaries

### Frontend
- Handle authentication, map display, GPS permissions, route recording, and capture status.
- Detect candidate loops for user experience only.
- Use shared API types and display pending, successful, and rejected states.
- Never submit trusted scores, final capture areas, or ownership assignments.

### API
- Validate request structure, field types, authentication context, and configured request limits.
- Use the authenticated user's identity rather than a client-supplied player ID.
- Support idempotent request submission and status retrieval.
- Submit capture jobs to SQS.
- Do not perform expensive polygon intersection calculations.

### Worker
- Validate route samples and polygon geometry independently.
- Calculate areas using a suitable metric projection or geodesic method.
- Resolve overlapping territory according to `docs/GAME_RULES.md`.
- Safely handle duplicate messages, retries, and concurrent captures.
- Persist capture status and ownership changes consistently.

### Persistence
- Store durable capture state and territory ownership.
- Support current-area scoring and capture history.
- Define exact item schemas and access patterns in `docs/DATA_MODEL.md`.

## 5. Critical Engineering Constraints

- **Idempotency:** SQS provides at-least-once delivery. Processing the same capture more than once must not apply ownership changes twice.
- **Concurrency:** overlapping captures must not silently overwrite newer state. Define and test a coordination strategy for conflicting updates.
- **Consistency:** do not report a capture as successful until its required ownership changes are durable.
- **Geometry:** latitude and longitude are angular coordinates, not metres. Use appropriate geographic calculations.
- **Spatial queries:** DynamoDB does not natively perform arbitrary polygon-intersection queries. Define a spatial-index strategy before implementing territory lookup at scale.
- **Privacy:** do not expose exact private GPS routes publicly or include unnecessary location data in logs.
- **Failure handling:** retries, failed writes, duplicate events, and worker crashes must have documented outcomes.

A DynamoDB single-table design or a single SQS queue does not, by itself, guarantee correct concurrent polygon updates. The data model and worker must explicitly enforce the chosen consistency strategy.

## 6. Visual Direction

The intended style is Vaporwave / Retro-Pop / Neo-Brutalist, with bold typography, high-contrast map overlays, strong borders, and hard shadows.

Usability takes priority over decoration. GPS errors, permission denial, poor accuracy, loading, pending captures, and rejected captures must be clear. Ownership must not be communicated by color alone.

## 7. MVP Scope

Required:
- Authentication and GPS route recording.
- Closed-loop capture submission and server-side validation.
- Unclaimed-land capture and overlapping-territory transfer.
- Durable ownership state and current-area scoring.
- Basic leaderboard, capture status, and history.
- Idempotent asynchronous processing.
- Automated geometry, ownership, and failure-case tests.

Defer social features, alliances, seasons, power-ups, advanced anti-cheat, and real-time multiplayer effects until the core capture flow is reliable.

## 8. Decisions Still Required

Before production deployment or full integration, document and test:

1. The map provider and its costs/licensing.
2. The final API request, response, and error contract.
3. The DynamoDB item schemas and query access patterns.
4. The spatial-index strategy and geographic scope of the MVP.
5. The concurrency strategy for overlapping captures.
6. The atomicity and recovery strategy for ownership changes and capture status.
7. The calibrated route-validation thresholds.

These decisions must be recorded in the relevant documents rather than independently invented by frontend and backend contributors.

## 9. Source of Truth

- `docs/ARCHITECTURE.md` — system components and engineering boundaries.
- `docs/GAME_RULES.md` — validation, ownership, and scoring behavior.
- `docs/API_CONTRACT.md` — HTTP interface and error behavior.
- `docs/DATA_MODEL.md` — persistence schemas and access patterns.
- `docs/CONTRIBUTING.md` — Git workflow, code review, and development rules.

Update the relevant document and tests whenever a shared decision changes.
'@ | Set-Content -Path .\docs\ARCHITECTURE.md -Encoding utf8

Write-Host "ARCHITECTURE.md replaced."
