# ConquestRunner — Backend API (`backend/api/`)

The Python API layer for ConquestRunner. It receives route submissions from
authenticated players, validates the request structure, and starts asynchronous
capture processing. It does **not** calculate territory: that is the worker's job
(`backend/worker/`).

> **Status: work in progress.** The code below is tested locally with fakes.
> Nothing here has been deployed or run against real AWS resources.
> Do **not** treat any endpoint as secured in production until the
> infrastructure and the Cognito authorizer are configured and verified.
> See [Not finished yet](#not-finished-yet).

Related documents:
[`docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md) (the contract),
[`docs/API_CONTRACT_CHANGES.md`](../../docs/API_CONTRACT_CHANGES.md) (proposed changes and shapes),
[`docs/DATA_MODEL.md`](../../docs/DATA_MODEL.md) (draft DynamoDB design).

## Endpoints implemented

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/v1/captures` | Validate a route and queue it for processing |
| `GET` | `/api/v1/captures/{captureId}` | Return the status of the caller's own capture |
| `GET` | `/api/v1/health` | Return `{"status": "healthy"}` |

## How a submission flows

```
Client ──POST──> API Gateway (JWT authorizer) ──> http_api.handle_request
                                                     │ identity = verified "sub" claim
                                                     │ validate header + body
                                                     ▼
                                              CaptureService.submit
                                                     │ 1. record  (status RECEIVED, internal only)
                                                     │ 2. pack the route (JSON -> gzip -> base64)
                                                     │ 3. send ONE message to SQS
                                                     │ 4. status -> PENDING
                                                     ▼
                              202 Accepted  (only after step 3 succeeded)
```

- The route travels inside the SQS message, compressed (technical lead's MVP decision).
  10,000 samples are about 134 KiB for a realistic route and about 321 KiB in the worst
  case. A hard size check runs after compression (limit: 1 MiB).
- If step 2 or 3 fails, the client gets `503` and is **never** told the request was
  accepted. The client retries with the same `Idempotency-Key`; the steps are repeated safely.
- A retry of an accepted request returns `200` with the current status. No second
  capture is created. The same key with a different route returns `409`.
- Delivery is at-least-once, so the worker must ignore duplicate messages for one `captureId`.

## Code layout

| File | Responsibility |
|---|---|
| `http_api.py` | HTTP only: reads the API Gateway event, checks identity and headers, builds JSON responses |
| `request_validation.py` | Structure and range checks for the route (no game rules) |
| `capture_service.py` | The submit and status rules, idempotency, retry-safe order of steps |
| `ports.py` | Interfaces the service depends on (repository, route store, queue) and shared types |
| `inline_route_store.py` | Packs the route as gzip + base64 for the queue message |
| `sqs_queue.py` | Builds the message, checks its size, sends it to SQS |
| `dynamodb_repository.py` | Stores capture records in DynamoDB (draft design in `docs/DATA_MODEL.md`) |
| `capture_lambda.py` | Wires everything for Lambda: reads the environment variables, creates AWS clients on the first request, calls `http_api.handle_request` |
| `errors.py` | Error codes and `ApiError` |
| `models.py`, `config.py` | `GpsSample` type; limits |
| `tests/` | Unit tests. `tests/fakes.py` holds in-memory test fakes |

`handler.py` belongs to the technical lead and is **not changed** in this folder. When it is
integrated, it can call `lambda_handler` from `capture_lambda.py`.

## Environment variables

`capture_lambda.py` reads these two variables. The **names are proposed** and not yet agreed with
the technical lead, so `infrastructure/template.yaml` must match whatever is decided.

| Variable | Used for |
|---|---|
| `CAPTURE_QUEUE_URL` | SQS queue that receives the capture jobs |
| `CAPTURES_TABLE_NAME` | DynamoDB table that holds the capture records |

If one is missing, the API returns a generic `500` and logs only the variable **name**.
Importing `capture_lambda.py` never contacts AWS; clients are created on the first request.

## Run the tests locally

No AWS account, credentials or internet access are needed for the tests.
Requires Python 3.11 or newer.

Run everything from the `backend/api` folder.

**Windows (PowerShell)**

```powershell
cd backend\api
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only if scripts are blocked
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
```

**macOS / Linux**

```bash
cd backend/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

Expected result: all tests pass (currently 184).

Lint and format checks (run from `backend/api`, not from the repository root):

```
python -m ruff check .
python -m ruff format --check .
```

Dependencies are kept separate from the worker's:
`requirements.txt` is what the Lambda needs (`boto3`), `requirements-dev.txt`
adds test and lint tools. The API has no `package.json`.

## Security notes

- The player identity comes **only** from the claims API Gateway verified
  (`requestContext.authorizer.jwt.claims.sub`). `playerId` in the body, or any
  identity header, is ignored; unknown body fields are rejected with `400`.
- GPS routes and coordinates are never written to logs. Unexpected errors return a
  generic `500` and the exception message is not logged.
- Responses are sent with `Cache-Control: no-store`.
- No credentials, account IDs or resource names are hard-coded. AWS clients are
  passed in, which is also what makes the code testable.
- AWS error details are never passed to the client.

## Not finished yet

*Proposed* items are not in the contract yet and need a team decision;
all of them are listed with their reasons in `docs/API_CONTRACT_CHANGES.md`.

**Never run on real AWS**
- Everything is tested only with fakes. `capture_lambda.py`, the DynamoDB repository and the
  SQS sender have not been run against real resources or with `sam local`.
- The DynamoDB table design is a draft proposal, not approved.
- The environment variable names are proposed, not agreed.

**Waiting for the technical lead**
- Integration of `handler.py` and `infrastructure/template.yaml` (both untouched here).
- The SQS queue must allow messages of 1 MiB (`MaximumMessageSize`); older queues may be set to 256 KiB.
- The shapes of the worker's `result` / `error` and the status transitions in `docs/DATA_MODEL.md`.

**Not included**
- Player stats, capture history and leaderboard endpoints.
- Stage-prefixed paths (`/prod/api/v1/...`), rate limiting, CORS, authorizer: infrastructure.
- Backend CI job (the workflow file belongs to the technical lead).

**Worker** (not part of this folder)
- Idempotent handling of duplicate messages, all geometry and ownership rules,
  and writing the final `SUCCEEDED` / `REJECTED` / `FAILED` status.
