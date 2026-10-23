
@'
# ConquestRunner — Contributing Guide

## 1. Purpose

This guide defines how the team collaborates on ConquestRunner.

All contributors must follow the shared architecture, game rules, API contract, and data model. If a decision changes, update the relevant documentation and tests.

## 2. Branching Strategy

- `main` is the stable integration branch.
- Do not commit directly to `main`.
- Create a feature branch for each task.
- Open a pull request (PR) to merge work into `main`.
- Keep changes focused and reasonably small.
- Do not force-push shared branches or rewrite shared history without team agreement.

Suggested branch names:

- `feat/ui-design`
- `feat/map-gps`
- `feat/api-handler`
- `feat/territory-worker`
- `fix/capture-validation`
- `test/geometry-cases`
- `docs/api-contract`

## 3. Initial Repository Setup

Each teammate should use the existing shared repository rather than creating a separate replacement repository.

If the repository is already cloned:

```powershell
git switch main
git pull origin main
git switch -c feat/your-task
```

Replace `feat/your-task` with a branch name that describes the task.

If the repository has not been cloned, clone the team's GitHub repository once, then follow the branch workflow above.

Before starting work, confirm that the working tree is clean:

```powershell
git status
```

Do not overwrite another contributor's local changes.

## 4. Daily Workflow

1. Start from an updated `main`.
2. Create or switch to your task branch.
3. Make changes only within the agreed task scope.
4. Run relevant checks and tests locally.
5. Review the diff for unrelated changes, secrets, and accidental generated files.
6. Commit with a descriptive message.
7. Push the branch to GitHub.
8. Open a PR targeting `main`.
9. Address review feedback and failing checks.
10. Merge only after the required review and CI checks pass.

Example commands:

```powershell
git switch main
git pull origin main
git switch -c feat/your-task

# Make and test your changes.

git status
git diff
git add path/to/your/files
git commit -m "feat: describe the change"
git push -u origin feat/your-task
```

Stage only files related to the task. Avoid `git add .` when unrelated or generated files may be present.

## 5. Pull Requests and Reviews

Every PR should explain:

- What changed.
- Why the change is needed.
- Which files or components are affected.
- How it was tested.
- Any known limitations or follow-up work.

Reviewers should check:

- The change follows the documented contracts.
- Existing behavior has not been broken unintentionally.
- Tests cover relevant behavior and edge cases.
- No credentials, tokens, private GPS data, or unrelated files were added.
- New dependencies are necessary and approved.
- Error handling and retry behavior are appropriate.
- Documentation is updated if a shared decision changes.

At least one teammate other than the author should review each PR. The technical lead coordinates integration and resolves cross-component conflicts.

Do not approve a change solely because CI passes. Review whether the implementation is correct.

## 6. Shared Contracts

The following files define shared project decisions:

- `docs/ARCHITECTURE.md` — component boundaries and system flow.
- `docs/GAME_RULES.md` — route validation, territory ownership, and scoring.
- `docs/API_CONTRACT.md` — HTTP requests, responses, statuses, and errors.
- `docs/DATA_MODEL.md` — persistence and access patterns.
- `docs/CONTRIBUTING.md` — collaboration and review workflow.

Before changing an endpoint, data shape, status value, ownership rule, or shared interface, discuss the change with affected contributors and update the relevant contract.

Do not independently invent request fields, endpoints, database keys, or status values.

## 7. Suggested Task Ownership

The initial division of responsibilities is:

### Technical lead — integration and territory logic
- Maintain repository structure and CI.
- Own territory geometry and ownership logic.
- Review integration across components.
- Coordinate architecture and data-model decisions.

### UI and design
- Build reusable UI components and screens.
- Follow the agreed visual direction and accessibility requirements.
- Use the documented API types rather than inventing backend responses.
- Provide loading, pending, success, rejection, and error states.

### Map and GPS
- Implement map display, GPS permissions, and route recording.
- Handle inaccurate samples, denied permissions, and interrupted tracking.
- Submit routes using the documented API contract.
- Treat client-side loop detection as provisional only.

### API and request handling
- Implement authenticated request handling and structural validation.
- Derive player identity from trusted authorizer claims.
- Implement idempotent submission and capture-status retrieval.
- Queue processing jobs using the documented message format.

These assignments may change by agreement. Changes should be communicated before work overlaps.

## 8. Backend and Frontend Boundaries

- The frontend must not decide authoritative territory ownership or scores.
- The API handler validates requests and enqueues jobs; it must not duplicate expensive geometry processing.
- The worker independently validates route data and performs authoritative geometry and ownership calculations.
- SQS messages should contain references and necessary metadata, not oversized route payloads.
- Duplicate messages and retries must not apply ownership changes twice.
- Do not report capture success before the required state is durably committed.

Refer to the architecture, game rules, API contract, and data model for the complete requirements.

## 9. Testing and CI

Before opening a PR:

- Run the relevant frontend lint, type-check, tests, and build.
- Run the relevant backend tests and formatting/lint checks once configured.
- Add tests for new behavior and important edge cases.
- Check that existing tests have not been removed or weakened just to make CI pass.
- Report checks honestly; do not claim a test passed unless it was run successfully.

The GitHub Actions workflow is the shared automated check. A PR with failing required checks must not be merged until the failure is understood and resolved.

If a check is unavailable or blocked by missing infrastructure, document the limitation instead of claiming it passed.

## 10. AI-Assisted Development

AI-generated code is a proposal, not verified implementation.

Contributors using AI must:

- Understand the generated code before submitting it.
- Verify that dependencies and APIs actually exist and are compatible with the project.
- Run the relevant tests and inspect the resulting diff.
- Follow the documented contracts and existing code style.
- Never invent successful test results, benchmark results, or deployment outcomes.
- Never paste secrets, access tokens, or private GPS data into prompts.
- Avoid large unrelated rewrites and unnecessary dependencies.
- Ask for review when uncertain about security, concurrency, geometry, or persistence behavior.

Do not accept code that changes shared behavior without updating its tests and documentation.

## 11. Commits and Repository Hygiene

Use clear commit messages, for example:

- `feat: add route recording`
- `feat: add capture submission handler`
- `fix: reject invalid route coordinates`
- `test: cover overlapping territory captures`
- `docs: clarify capture status responses`

Do not commit:

- AWS credentials, tokens, `.env` files, or private keys.
- Local dependency directories such as `node_modules`.
- Build outputs or temporary debug files unless explicitly required.
- Personal GPS recordings or other private data.
- Unrelated formatting changes that obscure the actual implementation.

Keep `.gitignore` updated for generated files and local configuration.

## 12. Integration and Conflict Resolution

If two tasks require different API fields, ownership semantics, or persistence behavior:

1. Pause the conflicting implementation.
2. Identify the affected contracts and components.
3. Agree on one shared design with the relevant contributors.
4. Update documentation and tests.
5. Resume implementation against the agreed design.

Do not resolve architectural disagreements by silently merging incompatible implementations.

When a merge conflict occurs, understand both changes before resolving it. Ask the relevant author when the intended behavior is unclear.

## 13. Definition of Done

A task is complete when:

- The implementation meets its agreed requirements.
- Relevant tests have been added or updated and run.
- Applicable lint, type-check, and build checks pass.
- Errors and failure cases have been considered.
- Shared contracts and documentation are updated when needed.
- The diff contains no unrelated changes or secrets.
- A teammate has reviewed the PR.
- Required CI checks pass and the PR is merged through the agreed workflow.

A task is not complete merely because the code compiles or an AI tool generated an implementation.
'@ | Set-Content -Path .\docs\CONTRIBUTING.md -Encoding utf8

Write-Host "CONTRIBUTING.md created."
