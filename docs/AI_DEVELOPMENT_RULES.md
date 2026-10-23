
@'
# ConquestRunner — AI Development Rules

## 1. Purpose

These rules apply whenever a contributor uses an AI assistant to write, modify, debug, or review project code.

AI-generated output is a proposal. The contributor remains responsible for understanding, testing, and reviewing the submitted implementation.

## 2. Read Before Coding

Before implementing a task, review the relevant project documentation:

- `docs/ARCHITECTURE.md`
- `docs/GAME_RULES.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `docs/CONTRIBUTING.md`

Check the existing source code, package configuration, tests, and naming conventions before asking AI to generate new files.

Do not assume that a planned component, dependency, endpoint, or infrastructure resource already exists.

## 3. Give AI a Bounded Task

Prompts should specify:

- The exact feature or bug.
- The files the contributor owns or may modify.
- Relevant interfaces and contract requirements.
- Expected behavior and error cases.
- Required tests.
- Dependencies that are allowed or prohibited.
- Commands that must be run to verify the change.

Ask AI to explain important assumptions and identify unresolved decisions before generating a large implementation.

Prefer small, reviewable changes over generating an entire application at once.

## 4. Do Not Invent Shared Interfaces

AI must not independently invent or change:

- HTTP endpoints, request fields, response fields, or error codes.
- Capture status values or idempotency behavior.
- DynamoDB keys, item attributes, or index definitions.
- SQS message formats.
- Territory ownership and scoring rules.
- Shared TypeScript types or Python interfaces.

Use the documented contracts as the baseline. If a contract is incomplete or conflicts with the implementation, stop and agree on a change with the affected contributors.

Update documentation and tests when a shared decision changes.

## 5. Verify Generated Code

Before submitting AI-assisted code:

1. Read the complete changed code.
2. Confirm imports, functions, types, and dependencies exist.
3. Check error handling and boundary conditions.
4. Run the relevant tests and quality checks.
5. Inspect the complete Git diff.
6. Remove debugging code and unrelated changes.
7. Explain any limitations that remain.

Never claim that code, tests, a deployment, or a benchmark succeeded unless the result was actually verified.

A plausible explanation or generated test is not evidence that the implementation works.

## 6. Testing Rules

- Add tests for new behavior and important edge cases.
- Preserve existing tests unless a behavior change is explicitly agreed upon.
- Never delete or weaken tests simply to make CI pass.
- Do not replace meaningful assertions with checks that always succeed.
- Use deterministic fixtures for geometry and route validation.
- Test failure and retry paths when changing asynchronous processing.
- Report untested behavior honestly.

For territory logic, test both the calculated geometry and the resulting ownership and area totals.

For API changes, test request validation, authentication assumptions, idempotency, and documented response shapes as applicable.

## 7. Security and Privacy

Never provide AI tools with:

- AWS access keys or secret keys.
- Authentication tokens, session cookies, or private credentials.
- Production secrets or private environment files.
- Real users' precise GPS recordings unless the use is explicitly authorized and necessary.

Do not hardcode credentials or disable authentication to make development easier.

Do not trust client-supplied player identity, ownership, or score values.

Validate untrusted input on the server. Frontend validation is not a security boundary.

Review generated code for unsafe logging, exposed location data, excessive permissions, injection risks, and accidental disclosure of internal errors.

## 8. Asynchronous Processing and Data Integrity

Changes involving SQS, DynamoDB, or the worker must consider:

- Duplicate message delivery.
- Retries and uncertain outcomes.
- Worker crashes before and after persistence.
- Concurrent captures that affect overlapping territory.
- Conditional writes and stale versions.
- Partial updates and recovery.
- Consistency between ownership, capture status, scores, and spatial-index entries.

Do not assume that a queue, a mutex in one process, or a single-table schema automatically solves distributed concurrency.

If the correct commit or recovery strategy is unclear, document the uncertainty and ask for review rather than inventing a guarantee.

## 9. Dependencies and Infrastructure

Do not add a dependency, cloud service, database, queue, or infrastructure resource without checking with the technical lead.

Before proposing a dependency, explain:

- Why it is necessary.
- Whether an existing dependency can solve the problem.
- Its maintenance and licensing implications.
- Its cost and operational impact.
- How it will be tested.

Do not deploy AWS resources or create paid services without team approval.

Do not assume a free tier guarantees that a service will remain free.

## 10. Repository and File Boundaries

- Work on the assigned feature branch.
- Modify only the files needed for the task.
- Do not overwrite another contributor's work.
- Do not reformat unrelated files.
- Do not commit generated dependency directories, build artifacts, secrets, or private data.
- Do not change CI or project configuration without understanding the impact.
- Ask before making broad refactors or adding new architectural layers.

Before committing, inspect:

```powershell
git status
git diff
```

Stage only the files related to the task.

## 11. AI Review Checklist

Before opening a pull request, confirm:

- [ ] I understand the code I am submitting.
- [ ] The implementation follows the relevant project contracts.
- [ ] I did not invent incompatible interfaces or data formats.
- [ ] I did not add unapproved dependencies or services.
- [ ] I considered relevant error and failure cases.
- [ ] I added or updated appropriate tests.
- [ ] I ran the checks relevant to my changes.
- [ ] I reviewed the full diff.
- [ ] I did not include secrets, private GPS data, or unrelated files.
- [ ] I documented unresolved limitations.
- [ ] I have not claimed verification that I did not perform.

## 12. When to Ask for Help

Ask the technical lead or affected contributor before proceeding when:

- Requirements contradict the documented rules.
- An API or data model change affects another task.
- Territory updates may violate ownership or scoring invariants.
- Concurrency or recovery behavior is unclear.
- A proposed change introduces a new dependency or cloud cost.
- Tests pass but the correctness of the behavior is uncertain.
- AI proposes a broad rewrite unrelated to the assigned task.

It is better to resolve an unclear contract before implementation than to integrate several incompatible versions later.

## 13. Final Principle

Use AI to accelerate implementation, explanation, and testing—not to replace engineering judgment.

The team is responsible for the correctness, security, maintainability, and demonstrated behavior of every merged change.
'@ | Set-Content -Path .\docs\AI_DEVELOPMENT_RULES.md -Encoding utf8

Write-Host "AI_DEVELOPMENT_RULES.md created."
