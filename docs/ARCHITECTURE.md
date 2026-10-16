Territory Run — System Architecture & Team Responsibilities
Project: Territory Run
Version: 1.0 — Initial Architecture
Project Type: Gamified GPS Running / Territory-Conquest SPA
Team Size: 4 members
Development Period: 5–6 months
Architecture: AWS Serverless
Repository: territory-run

1. Project Overview
Territory Run is a gamified running application where players capture geographic territory by physically running closed loops.
Players track their routes using GPS. When a valid loop is completed, the application submits a capture request to the backend. The backend validates the route, calculates the polygon area, resolves overlaps with existing territories, updates ownership and scores, and returns the capture result.
The application combines fitness tracking, competitive gameplay, real-time visual feedback, and asynchronous geospatial processing.
Core gameplay loop
1. A player starts a running session.
2. The frontend tracks GPS coordinates and draws the route on the map.
3. The application detects a potential closed loop.
4. The player submits the route for territory capture.
5. The backend validates the capture request.
6. A background worker calculates the new territory and resolves conflicts.
7. The database records the ownership and scoring changes.
8. The player sees the result on the map and leaderboard.
Core principle: The frontend provides the gameplay experience, but the backend is the authoritative source of territory ownership and scores.

2. Project Objectives
- Deliver a playable, polished web application.
- Implement GPS-based route tracking and polygon capture.
- Support multiple players and overlapping territory claims.
- Process captures asynchronously using AWS SQS and Lambda.
- Maintain consistent territory ownership and scoring.
- Build a maintainable codebase with automated tests and CI/CD.
- Keep development costs at ¥0 where practical, using local development and eligible free allowances.
- Produce a portfolio-quality project with documented architecture and engineering decisions.

3. Technology Stack
Layer	Technology	Responsibility
Frontend	React + TypeScript	Application UI and client-side logic
Build tooling	Vite	Development server and production builds
Styling	Tailwind CSS	Visual design system
Mapping	Mapbox GL JS or an approved alternative	Map rendering and route visualization
GPS	Browser Geolocation API	Location tracking
Frontend testing	Vitest + React Testing Library	Component and logic tests
Authentication	Amazon Cognito	Sign-up, sign-in and JWTs
API	Amazon API Gateway	HTTPS endpoints and JWT authorization
API compute	AWS Lambda	Request validation and job submission
Async processing	Amazon SQS	Capture event buffering
Worker	Python 3.11 + Shapely	Polygon validation and spatial calculations
Database	Amazon DynamoDB	Players, territories, captures and scores
Infrastructure	AWS SAM / CloudFormation	Infrastructure as code
Backend testing	pytest	Unit and integration tests
Python quality	Ruff	Linting and formatting
Frontend quality	ESLint + Prettier	Linting and formatting
CI/CD	GitHub Actions	Automated validation and deployment workflows
Version control	Git + GitHub	Collaboration and code reviewTechnology rules
- Use TypeScript for frontend application code.
- Use Python for the territory-processing worker.
- Use the standard AWS SDKs for AWS integrations.
- Avoid adding libraries without a clear technical reason.
- Pin dependencies and commit lockfiles.
- Never commit credentials, access tokens, or secrets.
- Do not introduce Redis or Kafka into the initial architecture; SQS is the designated asynchronous queue.
- Map providers and font licenses must be checked before production deployment.

4. System Architecture
4.1 High-level architecture
                    PLAYER
                      |
                      v
            +---------------------+
            | React SPA           |
            | TypeScript + Vite   |
            | Tailwind CSS        |
            +---------------------+
                      |
             Route 53 / CloudFront
                      |
                      v
            +---------------------+
            | Amazon Cognito      |
            | Authentication      |
            | JWT tokens          |
            +---------------------+
                      |
                      v
            +---------------------+
            | API Gateway         |
            | JWT Authorizer      |
            +---------------------+
                      |
                      v
            +---------------------+
            | API Lambda          |
            | Validate request    |
            | Create capture job  |
            +---------------------+
                      |
                +-----+------+
                |            |
                v            v
          DynamoDB         SQS Queue
          Metadata            |
                              v
                     +------------------+
                     | Worker Lambda    |
                     | Python + Shapely |
                     +------------------+
                              |
                              v
                     +------------------+
                     | DynamoDB         |
                     | Territories      |
                     | Capture records  |
                     | Scores           |
                     +------------------+
Important clarification: This is a serverless architecture using managed cloud services, not a decentralized system. Territory ownership is coordinated by the backend and stored centrally in DynamoDB.
4.2 Frontend responsibilities
The React SPA is responsible for:
- Rendering the user interface.
- Managing authentication state.
- Requesting GPS permissions.
- Tracking and displaying the route.
- Detecting candidate closed loops.
- Submitting capture requests.
- Displaying pending, successful, and rejected captures.
- Displaying player statistics, territory details, and leaderboard data.
The frontend must not be trusted to determine final territory ownership or authoritative scores.
4.3 API Lambda responsibilities
The API Lambda is responsible for:
- Receiving authenticated requests from API Gateway.
- Validating request structure, field types, coordinate limits and payload size.
- Obtaining the player identity from trusted authorizer claims.
- Creating or accepting an idempotency key.
- Recording or tracking capture-request status as required by the data model.
- Sending the capture event to SQS.
- Returning an HTTP response with a capture identifier.
The API Lambda must not perform expensive polygon intersection calculations.
A successful enqueue should normally return 202 Accepted, indicating that processing has been accepted but is not yet complete.
4.4 Worker Lambda responsibilities
The worker Lambda is responsible for:
- Unpacking SQS messages.
- Validating capture events again where appropriate.
- Rejecting malformed or invalid polygons.
- Converting geographic coordinates into a suitable projected coordinate system for planar area calculations.
- Finding potentially intersecting territories through a spatial-index strategy.
- Calculating intersections and differences with Shapely.
- Resolving ownership changes according to the game rules.
- Updating territory geometry, scores, and capture status consistently.
- Handling retries and duplicate delivery safely.
Shapely is a planar geometry library. Coordinates must not be treated as meters when they are expressed in latitude and longitude degrees.
4.5 DynamoDB responsibilities
DynamoDB stores persistent game state.
The initial design uses a single-table pattern with PK and SK, plus any required secondary indexes.
The exact item schemas must be defined in docs/DATA_MODEL.md before the worker and API are implemented independently.
The data model must account for:
- Player profiles.
- Territory geometry and ownership.
- Capture request status.
- Idempotency records.
- Capture history.
- Scores and leaderboard queries.
- Spatial-index entries for finding candidate territories.
A PK/SK table alone does not provide efficient arbitrary polygon intersection queries. The implementation must include a suitable spatial-index strategy, such as H3 cell indexing, and then use Shapely for precise geometry calculations.

5. Gameplay Rules
The backend is authoritative for every capture.
5.1 Route validation
The backend must validate:
- Coordinate ranges and types.
- Minimum number of valid points.
- Polygon closure and geometric validity.
- Self-intersections.
- Minimum and maximum permitted territory area.
- Maximum route length and request size.
- Implausible timestamps, speeds, and location jumps.
- Duplicate capture requests.
GPS accuracy checks and anti-spoofing heuristics reduce abuse but cannot prove that a runner physically completed a route.
5.2 Territory ownership
Initial proposed rules:
1. A new capture must pass validation before affecting existing territory.
2. Existing territory overlapping a valid capture loses the overlapping region.
3. The new capture claims the eligible area according to the approved game rules.
4. Scores are calculated from the resulting owned area, not blindly from the submitted polygon.
5. Territory ownership and score changes must remain consistent.
6. A rejected capture must not change ownership or scores.
7. Reprocessing the same capture event must not award points twice.
The team must explicitly decide how neutral land, disconnected territory fragments, minimum remaining territory size, and ties are handled.
5.3 Concurrency
Two players may submit overlapping captures simultaneously.
The worker must not read an old territory state and overwrite a newer update without detecting the conflict.
Use an appropriate concurrency strategy, such as conditional writes, optimistic version checks, or transactional writes with a well-defined conflict-retry process.
SQS Standard queues provide at-least-once delivery. The system must therefore support idempotent processing.
For the first release, a modest geographic scope and controlled capture-processing concurrency are preferable to an unnecessarily complex global spatial-processing system.

6. Visual Design System
6.1 Art direction
Style: Vaporwave / Retro-Pop / Neo-Brutalist / Arcade Athletics.
The application should feel like a retro sports tournament poster combined with a modern territory-control game.
Visual characteristics:
- Bright turquoise backgrounds and map surfaces.
- Neon yellow route lines and important gameplay actions.
- Neon pink, teal, and sunset orange accents.
- Heavy black outlines.
- Hard offset shadows.
- Angular cards and buttons.
- Bold, italicized display typography.
- Sticker-like status indicators and playful rotations.
- Strong contrast between map geometry and interface elements.
6.2 Design tokens
Suggested initial tokens:
Token	Value	Usage
water	#43E7E5	Main background and map accents
neon-yellow	#FFF000	Active GPS route and primary actions
hot-pink	#FF4FA3	Competitive accents
sunset-orange	#FF7A35	Warnings and secondary actions
deep-teal	#073B3A	Dark surfaces and contrast
ink	#000000	Borders and hard shadows
paper	#FFF9E8	Card backgrounds
white	#FFFFFF	High-contrast text and surfacesThese values are the initial design palette and may be refined through a shared design review.
6.3 Component styling
Borders:
border: 4px solid #000000;
Hard shadows:
box-shadow: 6px 6px 0 0 #000000;
Corners:
- Prefer sharp or minimally rounded corners.
- Use rotation sparingly for decorative cards and stickers.
- Keep important controls aligned and predictable.
6.4 Typography
- Display headings: heavy, geometric, italicized fonts.
- Body text: highly readable sans-serif.
- Numeric scores: bold and visually prominent.
- Error messages: clear, direct, and accessible.
6.5 UI design rules
- The active GPS route must remain visually distinguishable from captured territory.
- Every player territory must have a distinguishable color.
- Do not communicate ownership by color alone; use labels, patterns, or other cues where appropriate.
- Loading, GPS permission denial, poor GPS accuracy, network errors, pending captures, and rejected captures must have designed states.
- Mobile screens take priority because users will interact with the app while running.
- Avoid excessive animation, clutter, and rotation around map controls.
- Accessibility and readable contrast take precedence over decorative effects.

7. Application Features
7.1 MVP — Required features
Authentication
- Sign up and sign in.
- Authenticated API access.
- Sign out and session handling.
Map and tracking
- Interactive map.
- GPS permission handling.
- Start and stop tracking.
- Live route rendering.
- GPS accuracy display.
- Candidate loop detection.
Territory conquest
- Submit a completed route.
- Show capture processing status.
- Validate polygon geometry.
- Calculate area and overlaps.
- Update territory ownership.
- Display success or rejection feedback.
Player system
- Player profile.
- Total score and owned area.
- Territory display.
- Capture history.
Engineering
- Persistent storage.
- Asynchronous capture processing.
- Duplicate-event protection.
- Error handling.
- Automated tests.
- CI pipeline.
- Deployment and documentation.
7.2 Stretch features
Only implement these after the MVP is stable:
- Leaderboards with more advanced ranking options.
- Real-time capture notifications.
- Friends and rivalries.
- Achievements and daily challenges.
- Seasonal competitions.
- Advanced anti-cheat detection.
- Push notifications.
- Advanced spatial optimization.
- Live multiplayer updates through a dedicated push mechanism.
Stretch features must not delay a reliable core gameplay loop.

8. Team Responsibilities
Four members share responsibility for the finished product. Each module has a primary owner, but every contribution must follow the same architecture and review process.
Member 1 — Project Lead / Backend & Infrastructure
Primary owner: System architecture, integration, territory engine, AWS infrastructure and CI/CD.
Responsibilities
- Maintain architecture and technical documentation.
- Define API contracts and the database data model.
- Implement and review the core polygon and territory-ownership logic.
- Design capture processing and concurrency protection.
- Maintain the AWS SAM infrastructure template.
- Maintain GitHub Actions workflows.
- Review pull requests and resolve integration conflicts.
- Coordinate testing, deployment, and releases.
- Track project scope, milestones, and technical risks.
Main technologies
- Python 3.11.
- Shapely.
- AWS Lambda, SQS and DynamoDB.
- AWS SAM / CloudFormation.
- GitHub Actions.
- pytest and Ruff.
Primary directories
- backend/worker/
- infrastructure/
- .github/
- docs/
- tests/integration/
Deliverables
- Approved architecture and data model.
- Working territory-processing engine.
- Reliable asynchronous capture pipeline.
- CI and protected-branch workflow.
- Deployment documentation and integration tests.
Member 2 — Frontend Design System / UI
Primary owner: Shared UI components and visual consistency.
Responsibilities
- Implement the agreed visual design system.
- Build reusable buttons, cards, badges, dialogs, navigation, and layouts.
- Configure Tailwind design tokens.
- Implement responsive layouts and reusable typography styles.
- Ensure accessibility and visual consistency.
- Write component tests.
- Coordinate component interfaces with the other frontend members.
Main technologies
- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- React Testing Library.
- Vitest.
Primary directories
- frontend/src/components/ui/
- frontend/src/styles/
- frontend/src/assets/
Deliverables
- Shared component library.
- Consistent visual tokens.
- Responsive UI foundations.
- Reusable and tested components.
Member 3 — Map / GPS Tracking
Primary owner: Map integration, location tracking, and route capture interaction.
Responsibilities
- Integrate the selected map provider.
- Implement GPS permission and tracking states.
- Draw the live running route.
- Maintain the local coordinate history.
- Detect candidate closed loops.
- Display GPS accuracy and tracking errors.
- Submit capture requests through the shared API client.
- Test location-denied, poor-accuracy, and network-failure cases.
Main technologies
- React.
- TypeScript.
- Browser Geolocation API.
- Mapbox GL JS or the approved map alternative.
- Vitest.
- React Testing Library.
Primary directories
- frontend/src/features/tracking/
- frontend/src/features/map/
Deliverables
- Working map and live route.
- GPS tracking controls.
- Candidate loop detection.
- Capture submission interface.
- Tests for tracking and route-processing logic.
Member 4 — Player Experience / Game UI
Primary owner: Player profiles, score displays, capture history, and leaderboard screens.
Responsibilities
- Build the player profile interface.
- Display player statistics and owned territory.
- Implement capture history and status views.
- Build the leaderboard interface.
- Integrate approved API response types.
- Implement loading, error, empty, and success states.
- Use mock data only through the agreed development fixtures.
- Write component and interaction tests.
Main technologies
- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- Vitest.
- React Testing Library.
Primary directories
- frontend/src/features/profile/
- frontend/src/features/leaderboard/
- frontend/src/features/history/
Deliverables
- Profile and statistics screens.
- Leaderboard.
- Capture history.
- Tested data-display components.
Shared responsibilities
All members must:
- Use Git branches and pull requests.
- Read architecture documentation before implementing features.
- Follow the shared TypeScript and Python conventions.
- Add tests for meaningful logic.
- Report actual test results.
- Document new environment variables and dependencies.
- Review feedback and fix integration issues.
- Avoid merging unreviewed changes directly into main.
Primary ownership is not permission to work in isolation. Shared contracts and cross-module reviews remain mandatory.

9. Repository Structure
territory-run/
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   └── ui/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── tracking/
│   │   │   ├── map/
│   │   │   ├── profile/
│   │   │   ├── leaderboard/
│   │   │   └── history/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── styles/
│   ├── package.json
│   └── package-lock.json
├── backend/
│   ├── api/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── worker/
│       ├── handler.py
│       ├── territory.py
│       ├── validation.py
│       ├── storage.py
│       ├── requirements.txt
│       └── tests/
├── infrastructure/
│   └── template.yaml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACT.md
│   ├── DATA_MODEL.md
│   ├── GAME_RULES.md
│   ├── AI_DEVELOPMENT_RULES.md
│   └── CONTRIBUTING.md
├── tests/
│   └── integration/
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── .gitignore
└── README.md
This structure is the initial target. Keep it simple and avoid creating empty directories or abstractions without a concrete use.

10. Git and Collaboration Rules
Branch naming
main
feature/ui-design-system
feature/gps-tracking
feature/player-profile
feature/territory-worker
fix/polygon-validation
Workflow
1. Pull the latest main.
2. Create a feature branch.
3. Implement one bounded task.
4. Run local linting, tests, and builds.
5. Commit with a descriptive message.
6. Push the branch.
7. Open a pull request.
8. Wait for CI and review.
9. Fix requested changes.
10. Merge only when required checks pass and approval is complete.
Protect main with required CI checks and pull-request review. Do not commit directly to main.
Commit message examples
feat: add live GPS route rendering
fix: reject self-intersecting capture polygons
test: cover duplicate capture processing
docs: define territory ownership rules
ci: add frontend type-checking

11. AI-Assisted Development Rules
AI-generated code must be treated as a proposal, not as verified software.
Every task prompt must specify:
- Project context.
- Assigned module and file ownership.
- Existing interfaces and dependencies.
- Exact required behavior.
- Acceptance criteria.
- Required tests.
- Files that must not be modified.
- Expected final report.
AI coding restrictions
- Do not invent API endpoints or data schemas.
- Do not rewrite unrelated files.
- Do not silently change shared interfaces.
- Do not introduce unapproved dependencies.
- Do not remove tests to make CI pass.
- Do not claim that unexecuted tests passed.
- Do not commit secrets or credentials.
- Do not use placeholders in tasks declared complete.
- Do not merge generated code without review.
When a task depends on an undocumented decision, stop and request clarification.

12. CI Requirements
Every pull request targeting main must run the applicable checks.
Frontend
- Dependency installation from the committed lockfile.
- ESLint.
- TypeScript type checking.
- Unit and component tests.
- Production build.
Backend
- Dependency installation.
- Python syntax checks.
- Ruff linting and formatting checks.
- Type checking where configured.
- pytest unit tests.
- Territory geometry tests.
Infrastructure
- Validate the AWS SAM template.
- Check infrastructure configuration for accidental secrets.
- Add deployment or integration checks when the pipeline is ready.
A passing CI run is necessary but does not replace code review or end-to-end testing.

13. Development Timeline
Month 1 — Foundation
- Set up the repository and development environment.
- Agree on API contracts and game rules.
- Establish CI and Git workflow.
- Prototype polygon calculations.
- Build the initial design system.
Month 2 — Core frontend
- Implement the map and GPS tracking.
- Implement candidate loop detection.
- Build profiles and initial game UI.
- Test the territory engine locally.
Month 3 — Backend integration
- Implement authentication.
- Build API Lambda and SQS processing.
- Implement DynamoDB access and territory updates.
- Connect frontend capture submission to the backend.
Month 4 — Multiplayer correctness
- Complete overlapping territory logic.
- Implement idempotency and concurrency handling.
- Add capture history and score updates.
- Run end-to-end tests.
Month 5 — Stabilization
- Improve GPS and error handling.
- Add monitoring and security checks.
- Fix integration bugs.
- Conduct user testing.
- Complete deployment documentation.
Month 6 — Release and presentation
- Deploy the stable release.
- Resolve remaining high-priority bugs.
- Prepare the demo and project presentation.
- Document technical decisions and limitations.
If the project has only five months, freeze new features earlier and prioritize a reliable, demonstrable MVP.

14. Definition of Done
The project is considered ready for its final demonstration when:
- Players can authenticate.
- GPS routes can be tracked and visualized.
- Valid closed loops can be submitted.
- The backend validates capture requests.
- The worker calculates territory changes correctly.
- Overlapping captures produce deterministic ownership results.
- Duplicate processing does not award duplicate points.
- The frontend displays capture outcomes and player scores.
- Automated tests cover important gameplay and failure cases.
- CI passes for the release candidate.
- The application is documented and deployable.
- The team can explain the architecture and demonstrate how the system handles failures.

15. Final Engineering Principles
1. Correctness before feature count.
2. Backend authority for territory ownership and scores.
3. Clear module boundaries and stable contracts.
4. Automated testing before integration.
5. Idempotent and concurrency-safe capture processing.
6. Security and privacy by design.
7. Consistent visual design across the application.
8. Small pull requests and continuous integration.
9. No unnecessary infrastructure or dependencies.
10. Every team member understands the code they contribute.
Project goal: Deliver a visually distinctive running game supported by a reliable, well-tested serverless architecture that the entire team can understand, maintain, and confidently present.