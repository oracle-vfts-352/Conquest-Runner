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


### Backend and infrastructure

- Keep the backend authoritative for route validation, territory ownership, and scoring.
- Use API Gateway and Cognito JWT authorization for authenticated API requests.
- Use SQS to separate capture submission from heavier geometry processing.
- Treat asynchronous processing as potentially retried or duplicated; design for idempotency.
- Keep the SQS message small. Store route data in the data layer and pass a capture reference to the worker.
- Do not assume DynamoDB and SQS can participate in one atomic transaction. Document and test recovery from partial failures.
- Use infrastructure as code. Prefer AWS SAM / CloudFormation so resources can be reviewed and recreated.
- Develop locally first. Do not deploy paid or potentially billable resources without understanding the cost and cleanup process.

### Gameplay and data

- The backend must validate GPS samples and capture geometry before changing territory ownership.
- Initial validation thresholds in `docs/GAME_RULES.md` are proposals, not final gameplay balance.
- Define behavior for overlapping territories, simultaneous captures, retries, and failed worker processing explicitly.
- Keep player identity derived from trusted authentication claims, not a client-supplied player ID.
- Protect GPS route data as sensitive location information. Collect and retain only what the project needs.
- Treat the data model as a proposed design until it has been validated against actual query patterns and implementation requirements.

---

## 4. Documentation Status

The following project documentation files have been drafted or revised:

- `docs/ARCHITECTURE.md` — system architecture, component boundaries, technology choices, MVP scope, and open decisions.
- `docs/GAME_RULES.md` — capture validation, territory ownership, scoring, failure cases, and proposed thresholds.
- `docs/API_CONTRACT.md` — API endpoints, authentication, request and response behavior, idempotency, and error handling.
- `docs/DATA_MODEL.md` — proposed DynamoDB entities, access patterns, capture records, ownership, and concurrency considerations.
- `docs/CONTRIBUTING.md` — branch workflow, pull requests, reviews, testing, and definition of done.
- `docs/AI_DEVELOPMENT_RULES.md` — rules for bounded AI-assisted tasks, code verification, tests, security, and dependency changes.

These documents establish the current proposed contracts. They do not mean that the architecture or services have already been implemented.

### Documentation verification

- `git diff --check` passed for the current changes.
- The six documentation files above are modified in the working tree.
- `README.md` is unchanged.
- The documentation changes have not yet been committed or pushed.
- The documents still contain decisions that must be confirmed during implementation.

---

## 5. Current Git State

- Repository: `Conquest-Runner`
- Local branch: `main`
- Remote: `origin`
- Remote URL: `https://github.com/oracle-vfts-352/Conquest-Runner`
- The six documentation changes are currently uncommitted.
- Check `git status -sb` before staging or committing to confirm the actual state.

Do not claim that a commit or push succeeded until Git confirms it.

---

## 6. Team Collaboration Rules

- Keep shared gameplay rules, API contracts, and data models consistent across teammates.
- Assign each teammate a bounded task with clear file ownership and acceptance criteria.
- Before implementation, ask each contributor to read the relevant documentation and inspect the existing code.
- AI-generated code must be reviewed, tested, and integrated deliberately; generated code is not automatically correct.
- Avoid having multiple teammates independently redefine the same shared interface.
- Raise unclear requirements or conflicting decisions before making incompatible changes.
- Prefer small pull requests and reviewable changes over large, unverified batches.

---

## 7. Current Priorities

1. Complete and review `state.shiki.md`.
2. Review the six documentation changes and confirm the contracts are internally consistent.
3. Stage the intended documentation files and inspect the staged diff.
4. Commit and push the documentation checkpoint to GitHub.
5. Create a compact `AI_CONTEXT.md` for teammates using browser-based AI tools.
6. Establish the repository's CI workflow and verify it against the actual project files.
7. Begin implementation only after task ownership and shared contracts are clear.

---

## 8. Update Rules for Future Sessions

At the end of each meaningful work session:

1. Update the date and current milestone.
2. Record what changed and what was actually verified.
3. Record test and CI results accurately.
4. Separate implemented behavior from proposed architecture.
5. Record unresolved decisions, blockers, and the next concrete action.
6. Check `git status -sb` and note whether changes are uncommitted, committed, or pushed.
7. Never claim a deployment, test, commit, or push succeeded without evidence.

