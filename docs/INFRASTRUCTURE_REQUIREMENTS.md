# ConquestRunner — Infrastructure Requirements for the Capture API

> **Status: DRAFT for the technical lead. Nothing here has been deployed or tested on AWS.**
> Written from the code in `backend/api/`. It does not change `infrastructure/template.yaml`
> or `handler.py`; both belong to the technical lead.

Each item is labelled:

- **REQUIRED** — the code in `backend/api/` will not work without it.
- **PROPOSAL** — a suggestion. It was not measured or tested, and the lead may change it.

The API code never contacts AWS when it is imported, and its 200 tests use in-memory fakes only.
So everything below is **unverified on a real account** until the deployed integration test.

---

## 1. Environment variables

| Name | Status | Purpose |
|---|---|---|
| `CAPTURE_QUEUE_URL` | REQUIRED | Full URL of the SQS queue that receives capture messages |
| `CAPTURES_TABLE_NAME` | REQUIRED | Name of the DynamoDB table that stores capture records |

- A missing or blank value makes `GET /api/v1/ready` return `503` and every capture route return `500`.
  `GET /api/v1/health` is not affected.
- The names are **proposed by the API side** and not yet agreed. If the lead prefers other names,
  only the constants `QUEUE_URL_ENV` and `TABLE_NAME_ENV` in `backend/api/capture_lambda.py` change.
- No region variable is needed. The code calls `boto3.client("dynamodb")` and `boto3.client("sqs")`
  without a region, so it uses the `AWS_REGION` that the Lambda runtime sets itself.
- No secrets, keys or tokens are read from the environment.

## 2. IAM permissions for the API Lambda

The API Lambda needs **only** these actions (REQUIRED, from `dynamodb_repository.py` and `sqs_queue.py`):

| Service | Actions | Resource |
|---|---|---|
| DynamoDB | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` | The captures table ARN |
| SQS | `sqs:SendMessage` | The capture queue ARN |

Notes:

- No `Scan`, `Query`, `DeleteItem` or `BatchWrite*` is used. Please do not grant them.
- The conditional writes (`attribute_not_exists`, `status = RECEIVED`) need no extra permission.
- If the table or the queue is encrypted with a **customer-managed KMS key**, the Lambda role also
  needs `kms:GenerateDataKey` (SQS) and `kms:Decrypt`/`kms:GenerateDataKey` as the key policy requires.
  With AWS-managed keys nothing extra is needed. (PROPOSAL: AWS-managed keys for the MVP.)
- Basic logging permission (`AWSLambdaBasicExecutionRole`) is expected for CloudWatch Logs.
- The worker's permissions are the lead's design. For reference, the worker will at least need to read
  and delete from the queue and run `GetItem`/`UpdateItem` on the same table.

## 3. DynamoDB table

| Item | Status | Value |
|---|---|---|
| Partition key | REQUIRED | `PK` (String) |
| Sort key | REQUIRED | `SK` (String) |
| Capture item keys | REQUIRED | `PK = CAPTURE#<captureId>`, `SK = META` |
| Billing mode | PROPOSAL | On-demand (`PAY_PER_REQUEST`) |
| TTL attribute | not used | The API never sets one. Cleanup of records stuck in `RECEIVED` is still an open question |

Attribute layout and statuses: see `docs/DATA_MODEL.md` and `docs/CAPTURE_RECORD_PROPOSAL.md`.
Reads are strongly consistent (`ConsistentRead`), which is supported on a base table.

## 4. API Gateway (HTTP API)

**REQUIRED: payload format version 2.0.** The code reads `rawPath`, `requestContext.http.method`,
`requestContext.requestId` and `requestContext.authorizer.jwt.claims.sub`.

| Method | Path | Authorizer | Notes |
|---|---|---|---|
| `POST` | `/api/v1/captures` | Cognito JWT | Needs the `Idempotency-Key` header |
| `GET` | `/api/v1/captures/{captureId}` | Cognito JWT | |
| `GET` | `/api/v1/health` | **None** | Alive check |
| `GET` | `/api/v1/ready` | **None** | Readiness check (new) |

Points the lead must decide or check:

1. **Stage name (REQUIRED to check).** The handler compares `rawPath` with the exact paths above.
   For an HTTP API with a named stage (for example `prod`), `rawPath` may include the stage prefix
   (`/prod/api/v1/health`), and every route would then return `404`. Please use the `$default` stage,
   or tell the API side so the path matching can be changed. To be verified on the first deploy.
2. **JWT authorizer.** Issuer is the Cognito user pool. The audience must match the token type that the
   client sends (an ID token carries `aud`; an access token carries `client_id`). The API code only
   needs the `sub` claim and works with either. Please tell the map member which token to send.
3. **Health and ready must be public** (no authorizer), because they must work without a login.
   They return no secrets and no personal data. (Whether they stay public is still listed as open in
   `docs/API_CONTRACT.md` section 10.)
4. **Payload limits.** The API rejects bodies over 2,000,000 bytes with `413`. API Gateway's own limit
   is 10 MB and Lambda's synchronous limit is 6 MB, so both are above ours.
5. **Gateway-made responses differ from our error format.** A `401` from the authorizer and a `429`
   from throttling come from API Gateway, not from our code, so their body is not
   `{"error":{"code","message"}}`. The map client must treat `401`/`429` by status code alone.
6. **Throttling (PROPOSAL).** Set stage or route throttling so that abuse is limited. The numbers are the
   lead's decision. The API code has no rate limiting of its own (`RATE_LIMITED` is not produced by it).
7. **Access logs.** Please do **not** log request bodies or the `Authorization` header in API Gateway
   access logs. The body contains the player's GPS route.

## 5. CORS (browser clients)

Configure CORS on the HTTP API. The Lambda adds **no** CORS headers itself. API Gateway answers the
`OPTIONS` preflight.

| Setting | Value | Status |
|---|---|---|
| Allowed methods | `GET`, `POST`, `OPTIONS` | REQUIRED for a browser client |
| Allowed headers | `authorization`, `content-type`, `idempotency-key` | REQUIRED for a browser client |
| Allowed origins | The frontend origin(s) | Not known to the API side. Please use explicit origins, not `*` |
| Allow credentials | Not needed (the token is sent in a header, not a cookie) | PROPOSAL |
| Exposed headers | None needed (the API returns no custom response headers) | |
| Max age | Optional, for example 600 seconds | PROPOSAL |

Without `idempotency-key` in the allowed headers, the browser blocks the capture request before it is sent.

## 6. SQS queue

| Item | Status | Value |
|---|---|---|
| `MaximumMessageSize` | **REQUIRED** | **1048576** (1 MiB) |
| Queue type | PROPOSAL | Standard queue. Duplicates are possible, the worker must be idempotent by `captureId` |
| Visibility timeout | PROPOSAL | At least 6 times the worker Lambda timeout (AWS guidance for Lambda event sources) |
| Dead-letter queue | PROPOSAL | Recommended, with a `maxReceiveCount` chosen by the lead |
| Message retention | PROPOSAL | Lead's decision |
| Encryption | PROPOSAL | SQS-managed encryption |

Why 1 MiB: the route is sent inside the message as gzip + base64. Measured on fake data, 10,000 samples is
about 134 KiB realistic and about 321 KiB worst case. Older queues default to 256 KiB, so the limit must be
raised explicitly. The API also refuses to send anything above 1 MiB (`413`).

Message body (one message per capture):

```json
{
  "schemaVersion": 1,
  "captureId": "capture_<32 hex>",
  "playerId": "<cognito sub>",
  "route": { "encoding": "gzip+base64", "data": "<base64 text>" }
}
```

The worker unpacks `route.data` with base64 decode, then gzip decompress, then JSON.
(`unpack_route` in `inline_route_store.py` does exactly this.)

## 7. Lambda: runtime, packaging, timeout, memory

| Item | Status | Value |
|---|---|---|
| Runtime | **REQUIRED** | Python **3.11 or newer**. The code parses timestamps ending in `Z` with `datetime.fromisoformat` and uses `datetime.UTC`, both need 3.11 |
| Handler | REQUIRED | `handler.lambda_handler`, where `handler.py` contains `from capture_lambda import lambda_handler` (agreed with the lead). `capture_lambda.lambda_handler` also works directly |
| Modules | **REQUIRED** | The flat modules in `backend/api/` must sit at the **root** of the package: `capture_lambda`, `capture_service`, `http_api`, `request_validation`, `errors`, `config`, `models`, `ports`, `inline_route_store`, `sqs_queue`, `dynamodb_repository`. The code uses plain imports such as `from models import ...`, so a package prefix or subfolder breaks them |
| Exclude from the package | PROPOSAL | `tests/`, `replay_request.py`, `request.json`, `.venv`, `pytest.ini`, `requirements-dev.txt` |
| Dependencies | REQUIRED | Only `boto3`, which the Lambda runtime already contains. `requirements.txt` pins `boto3==1.43.124`. Bundle it only if the lead wants that exact version |
| Architecture | no requirement | Pure Python, no native libraries |
| Timeout | PROPOSAL | 10 seconds. A request does one DynamoDB read, one write, one SQS send and one update. API Gateway allows at most 30 seconds |
| Memory | PROPOSAL | 256 MB. **Not measured.** A 2 MB body is parsed, gzip-compressed and base64-encoded in memory. Please check the real peak in CloudWatch after deploy and adjust |
| Reserved concurrency | no requirement | Lead's decision |

Logging behaviour (REQUIRED to know): the code never logs the event, the GPS route, claims or tokens.
On an error it logs only the exception type, the traceback frames and the request id.

## 8. Health and readiness: expected behaviour

Both routes are public (`GET`, no body, no `Idempotency-Key`). Both return `Content-Type: application/json`
and `Cache-Control: no-store`.

| Request | Situation | Status | Body |
|---|---|---|---|
| `GET /api/v1/health` | Handler is running (always) | `200` | `{"status":"healthy"}` |
| `GET /api/v1/ready` | Both env variables set and clients can be created | `200` | `{"status":"ready"}` |
| `GET /api/v1/ready` | A variable is missing or blank, or a client cannot be created | `503` | `{"error":{"code":"INTERNAL_ERROR","message":"The service is not ready."}}` |

- `/health` never builds the service. It works even when the configuration is missing.
- `/ready` checks the configuration and client creation only. It does **not** call DynamoDB or SQS, so it
  does not prove that the IAM permissions, the table or the queue are correct.
- The response never names the missing variables. Their names are written to the log only.
- `/ready` is not cached after a failure, so it turns `200` as soon as the configuration is fixed.

## 9. Smoke test after deployment (proposal)

Replace `<API_URL>` and `<TOKEN>` yourself. Never paste a real token into a chat, a commit or a document.

1. `GET <API_URL>/api/v1/health` -> `200`.
2. `GET <API_URL>/api/v1/ready` -> `200` (if `503`, read the CloudWatch log for the missing variable name).
3. `POST <API_URL>/api/v1/captures` without a token -> `401` (made by API Gateway).
4. `POST` with a token, an `Idempotency-Key` and a route of 4 or more fake samples -> `202` and a `captureId`.
5. The same request again -> `200` with the same `captureId`, and still **one** SQS message.
6. The same key with a different body -> `409`.
7. `GET <API_URL>/api/v1/captures/<captureId>` -> `200` with the current status.
8. Browser check: an `OPTIONS` preflight from the frontend origin with `idempotency-key` in
   `Access-Control-Request-Headers` is accepted.

## 10. Not covered here

- The worker, the territory logic and the final `result`/`error` shapes of a capture.
- Retention and cleanup of records stuck in `RECEIVED`.
- Throttling numbers, alarms, dashboards, and any production security review.
