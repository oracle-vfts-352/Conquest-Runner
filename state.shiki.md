# ConquestRunner — Project State

> **Purpose:** This file is the source of truth for project progress and the handoff document for future ChatGPT conversations.
>
> **Update rule:** Update this file after every meaningful milestone. Never mark a task complete unless it has been verified.

Last updated: 2026-10-23

---

## 1. Project Identity

**Project name:** ConquestRunner

**Project type:** GPS-based territory-conquest running game.

**Team:** 4 students total — me + 3 teammates.

**Timeline:** Approximately 5–6 months.

**Primary goal:** Deliver a working, well-engineered team project that demonstrates backend, cloud infrastructure, testing, CI/CD, collaboration, and system-design skills for software engineering internship applications in Japan.

**My role:** Technical lead / infrastructure engineer. I am responsible for establishing the project structure, architecture, CI, cloud infrastructure, integration standards, and code review. I will contribute code where needed, but should not become the only person capable of maintaining the project.

### Core gameplay

1. A player records a running route using GPS.
2. The player attempts to complete a closed loop.
3. The frontend submits the route to the backend.
4. The backend validates the route and calculates the captured polygon.
5. Valid captures claim unowned land and can take land from existing owners.
6. The system updates territory ownership and player scores.
7. Players can view the map and leaderboard.

**Core principle:** The server is authoritative. The frontend must never be trusted to decide final territory ownership or scoring.

---

## 2. Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Oxlint
- Vitest
- React Testing Library
- Mapbox GL JS or another approved map provider
- Browser Geolocation API

### Backend

- AWS Lambda for API handling
- AWS Lambda worker for territory calculations
- Python for geometry processing
- Shapely for polygon operations
- Amazon API Gateway HTTP API
- Amazon SQS for asynchronous processing
- SQS dead-letter queue for failed messages

### Data and authentication

- Amazon DynamoDB
- Amazon Cognito
- API Gateway JWT authorizer

### Infrastructure and engineering

- AWS SAM / CloudFormation
- GitHub Actions
- Git and GitHub
- VS Code
- Automated linting, type checking, tests, and builds

**Budget rule:** Prefer free local development and avoid deploying resources until their costs, free-tier eligibility, cleanup procedure, and security implications are understood.

**Important:** This is the intended architecture, not a claim that all these services have been implemented or deployed.

---

## 3. Architecture Rules

These decisions should guide implementation unless a documented reason justifies changing them.

