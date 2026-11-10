# ConquestRunner — Backend API (`backend/api/`)

The Python API layer for ConquestRunner. It receives route submissions from
authenticated players, validates the request structure, and starts asynchronous
capture processing. It does **not** calculate territory: that is the worker's job
(`backend/worker/`).

> **Status: work in progress.** The code below is complete for local use and tested with fakes.
> Nothing here has been deployed or verified against real AWS resources.
> Do **not** treat any endpoint as secured in production until the
> infrastructure and the Cognito authorizer are configured and tested.
> See [Not finished yet](#not-finished-yet).

The HTTP contract is in [`docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md).
This README describes the code, not the contract.

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
                                                     │ 2. store the route   (S3)
                                                     │ 3. send small message (SQS)
                                                     │ 4. status -> PENDING
                                                     ▼
                              202 Accepted  (only after step 3 succeeded)
```

- If step 2 or 3 fails, the client gets `503` and is **never** told the request was
  accepted. The client retries with the same `Idempotency-Key`; the steps are
  repeated safely.
- A retry of an accepted request returns `200` with the current status. No second
  capture is created.
- The same key with a different route returns `409`.
- The SQS message holds no GPS data, only where the route is stored. Delivery is
  at-least-once, so the worker must ignore duplicate messages for one `captureId`.

## Code layout

| File | Responsibility |
|---|---|
| `http_api.py` | HTTP only: reads the API Gateway event, checks identity and headers, builds JSON responses |
| `request_validation.py` | Structure and range checks for the route (no game rules) |
| `capture_service.py` | The submit and status rules, idempotency, retry-safe order of steps |
| `ports.py` | Interfaces the service depends on (repository, route store, queue) and shared types |
| `s3_route_store.py` | Saves the route to S3 (the "claim check") |
| `sqs_queue.py` | Sends the job message to SQS |
| `dynamodb_repository.py` | Stores capture records in DynamoDB (table design is a proposal, see [`docs/DATA_MODEL.md`](../../docs/DATA_MODEL.md)) |
| `handler.py` | The Lambda entry point: reads the environment variables, creates the AWS clients on the first request, and calls `http_api.handle_request` |
| `errors.py` | Error codes and `ApiError` |
| `models.py`, `config.py` | `GpsSample` type; limits |
| `tests/` | Unit tests. `tests/fakes.py` holds in-memory test fakes |

## Environment variables

`handler.py` reads these three variables. The **names are proposed** and not yet agreed with the
technical lead, so `infrastructure/template.yaml` must match whatever is decided.

| Variable | Used for |
|---|---|
| `ROUTE_BUCKET_NAME` | S3 bucket that holds the stored routes |
| `CAPTURE_QUEUE_URL` | SQS queue that receives the capture jobs |
| `CAPTURES_TABLE_NAME` | DynamoDB table that holds the capture records |

If one is missing, the API returns a generic `500` and logs only the variable **name**.
Importing `handler.py` never contacts AWS; clients are created on the first request.

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

Expected result: all tests pass (currently 189).

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
- Storage keys only accept `A–Z a–z 0–9 _ -`, so an identifier cannot change the
  folder structure.
- No credentials, account IDs or resource names are hard-coded. AWS clients are
  passed in, which is also what makes the code testable.

## Not finished yet

These items are open. Items marked *proposed* are not in the contract yet and need
a team decision.

**Never run on real AWS**
- Everything is tested only with fakes. The handler, the three adapters and the
  DynamoDB conditions have not been run against real resources or with `sam local`.
- The DynamoDB table design in `docs/DATA_MODEL.md` is a draft proposal, not approved.
- The environment variable names above are proposed, not agreed.

**Design decisions waiting for the technical lead**
- **S3 claim-check or compression.** 10,000 samples is about 1 MB of JSON, but one
  SQS message holds 256 KiB. The code follows the S3 claim-check proposal
  (contract section 4.3). Gzip + base64 would be about 137 KB, so it could also
  fit. Only `s3_route_store.py` (and the message) would change.
- The format of the stored `route.json`, the SQS message, and the worker's
  `result` / `error` shapes must be agreed with the worker owner.
- How the worker finds the route: it should read the bucket from its own
  configuration and check the key prefix instead of trusting the message.

**Assumptions not in the contract** (*proposed*)
- A retry of an already accepted request returns `200` (the first one returns `202`).
- A path the API does not handle returns `404` with code `NOT_FOUND`.
- Maximum request body is 2 MB (`MAX_BODY_BYTES`); minimum route length is 4
  samples (`MIN_SAMPLES`).
- Too many samples returns `413` with code `INVALID_REQUEST` (the contract's 413
  example uses that code). Errors from route validation use `INVALID_REQUEST`;
  `INVALID_ROUTE` is left for the worker.
- `UNAUTHORIZED` and `CAPTURE_NOT_FOUND` are used but missing from the error table
  in the contract.
- `/api/v1/health` needs no authentication.

**Infrastructure** (owned by the technical lead, not changed here)
- Authorizer, CORS, throttling, bucket policy and encryption, lifecycle/retention
  of stored routes, the dead-letter queue, and API paths when a stage name is
  part of the URL.
- Rate limiting and body-size limits at API Gateway level.

**Worker** (not part of this folder)
- Idempotent handling of duplicate messages, all geometry and ownership rules,
  and writing the final `SUCCEEDED` / `REJECTED` / `FAILED` status.