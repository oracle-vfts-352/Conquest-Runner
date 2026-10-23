ConquestRunner

Run your route. Claim the map. Take the territory.

ConquestRunner is a GPS-based territory-conquest running game where players turn real-world runs into territory. Run a closed loop to claim land, expand your area, and compete with other players by capturing territory they own.

The project is being developed by a four-person student team over a five-to-six-month development period, with an emphasis on backend correctness, asynchronous processing, geospatial computation, and reliable cloud architecture.

Project status: In development
Version: 0.1.0 — Initial development
Project type: Team software engineering project

Table of Contents

Overview

Gameplay

Features

Visual Direction

Technology Stack

Architecture

Getting Started

Repository Structure

Team Responsibilities

Testing and CI

Documentation

Development Principles

Overview

Territory Run combines outdoor running, GPS tracking, and competitive territory ownership.

Players record a running route using their device's GPS. When a valid closed loop is submitted, the backend calculates the enclosed area and determines the resulting territory ownership.

Unlike a conventional running tracker, the goal is not only to record distance and time. Players compete for control of geographic areas.

Gameplay

Run: Record a GPS route while moving outdoors.

Close the loop: Return near the starting point to form a candidate capture polygon.

Submit: Send the recorded route to the backend for validation.

Capture: Claim unowned land and take over the portions of other players' territory that overlap the valid capture.

Compete: View current territory ownership, area totals, capture history, and leaderboard rankings.

The backend determines the final result. The frontend can display a candidate capture, but it cannot independently award territory.

Features

Core gameplay

GPS route recording and map visualization.

Closed-loop capture attempts.

Server-side route validation.

Geospatial polygon processing.

Territory capture and ownership transfer.

Current territory area and leaderboard.

Capture status and history.

Reliability and security

Authenticated API requests.

Asynchronous capture processing.

Duplicate-request protection and idempotent workers.

GPS plausibility checks and request limits.

Consistent territory updates under concurrent captures.

Automated tests for geometry, ownership, and failure scenarios.

Planned enhancements

Potential future features include seasonal rankings, territory-theft notifications, teams, and additional gameplay mechanics. These are secondary to delivering a reliable core capture system.

Visual Direction

The interface uses a Vaporwave / Retro-Pop / Neo-Brutalist visual direction.

Design principles:

Saturated turquoise and teal map-inspired colors.

Neon yellow and hot-pink highlights.

Sunset-orange accents.

Thick black borders and hard offset shadows.

Sharp corners, bold geometric typography, and energetic layouts.

Responsive layouts and accessible controls.

The visual style should feel playful and competitive without sacrificing usability or readability.

Technology Stack

Layer

Technology

Frontend

React, TypeScript, Vite

Styling

Tailwind CSS and reusable UI components

Map

Mapbox GL JS or another approved mapping provider

Location

Browser Geolocation API

Authentication

Amazon Cognito

API

Amazon API Gateway and AWS Lambda

Asynchronous processing

Amazon SQS and worker Lambda

Geospatial processing

Python and Shapely

Persistence

Amazon DynamoDB

Infrastructure

AWS SAM / CloudFormation

Frontend testing

Vitest and React Testing Library

Backend testing

pytest

Code quality

ESLint, TypeScript checks, Ruff

CI

GitHub Actions

Note: This is the planned stack. Individual services and dependencies will be finalized as implementation begins. Map providers, AWS deployment, and any optional services must be configured before their corresponding features can run.

Architecture

flowchart TD
    A[React SPA] --> B[CloudFront / Route 53]
    B --> C[Amazon Cognito]
    C --> D[API Gateway]
    D --> E[API Lambda]
    E --> F[Amazon SQS]
    E --> G[(Amazon DynamoDB)]
    F --> H[Worker Lambda]
    H --> I[Geospatial Processing]
    I --> G
    G --> J[Territory and Leaderboard Results]
    J --> A

Request flow

The frontend records a route and submits it using an authenticated request.

API Gateway and the API handler validate authorization and request structure.

The API handler creates a capture job and enqueues it for asynchronous processing.

The worker validates the route and calculates the capture polygon.

The worker identifies affected territory, computes ownership changes, and persists the result safely.

The frontend retrieves the capture status and updated territory information.

The worker must be safe against duplicate queue deliveries and concurrent overlapping captures.

Architecture note: The diagram represents the intended logical flow. The implementation must define the exact order of persistence and queue publication, including failure recovery, so a capture request cannot be lost between database writes and SQS enqueueing. DNS, CDN, and authentication components will be introduced as part of deployment.

Getting Started

Prerequisites

Install the following tools before starting local development:

Node.js — use the version specified by the repository.

npm — included with Node.js.

Python — use the version pinned by the backend configuration.

Git.

Visual Studio Code.

AWS CLI and AWS SAM CLI will be required when the team begins local cloud-stack testing or deployment. They are not prerequisites for every frontend-only task.

1. Clone the repository

git clone <YOUR_GITHUB_REPOSITORY_URL>
cd territory-run

Replace the placeholder with the team's actual repository URL.

2. Start the frontend

cd frontend
npm ci
npm run dev

Open the local URL printed by Vite.

3. Set up the backend

Follow the backend-specific instructions in backend/README.md once the API and worker skeletons are available.

The backend setup should document Python environment creation, dependency installation, local testing, and required environment variables.

4. Configure environment variables

Create local environment files using the committed example templates, such as .env.example.

Do not commit real credentials, access tokens, AWS keys, or private environment files.

Current setup status

The commands above describe the intended development workflow. They may need adjustment until the repository, package scripts, dependency files, and backend entry points have been created.

Repository Structure

territory-run/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── backend/
│   ├── api/
│   └── worker/
├── infrastructure/
│   └── template.yaml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── GAME_RULES.md
│   ├── API_CONTRACT.md
│   └── DATA_MODEL.md
├── tests/
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── .gitignore
└── README.md

This is the intended repository layout; directories and files will be added as the project develops.

Team Responsibilities

Member

Primary responsibility

Member 1 — Project Lead

Architecture, backend integration, territory engine, infrastructure, CI, code review

Member 2 — UI / Design System

Reusable components, visual tokens, responsive layouts, accessibility

Member 3 — Map / GPS

GPS recording, route visualization, loop detection, capture submission UI

Member 4 — Player Experience

Profile, statistics, capture history, leaderboard UI

All members contribute to testing, documentation, reviews, and integration. Shared interfaces must be agreed upon before parallel implementation.

Testing and CI

GitHub Actions will automatically check submitted changes.

Planned checks include:

Frontend dependency installation and production build.

ESLint and TypeScript checks.

Frontend unit tests.

Python dependency installation.

Python linting and tests.

Backend validation and geometry regression tests.

Changes should be submitted through pull requests. The main branch should remain stable, and required CI checks should pass before merging.

Documentation

Document

Purpose

docs/ARCHITECTURE.md

System design, components, and data flow

docs/GAME_RULES.md

Capture mechanics, fairness, edge cases, and acceptance criteria

docs/API_CONTRACT.md

API endpoints, payloads, and error responses

docs/DATA_MODEL.md

DynamoDB keys, records, and ownership representation

Development Principles

Correctness before complexity: Implement a reliable core game before adding advanced features.

Backend authority: The server determines capture validity and territory ownership.

Explicit contracts: Frontend and backend must share documented request and response formats.

Reliable asynchronous processing: Design for duplicate messages, retries, and worker failures.

Testable geometry: Use deterministic fixtures for polygon and area calculations.

Secure by default: Keep credentials out of source control and minimize exposure of GPS data.

Reviewable code: Prefer small pull requests, clear naming, and focused modules.

Documented decisions: Update the architecture and rules whenever behavior changes.

Built as a collaborative software engineering project focused on geospatial computation, asynchronous processing, cloud architecture, and reliable application design.