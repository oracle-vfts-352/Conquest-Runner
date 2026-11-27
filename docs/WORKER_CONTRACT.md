# ConquestRunner — Worker Contract (API side)

> **Status: DRAFT. Not agreed by the team.** Nothing here is implemented in `backend/worker/`
> (all worker files are still empty placeholders) and nothing was run on AWS.
>
> This document describes the boundary between the capture API and the worker. It is **not** a design of
> the territory logic or of the game result. Those decisions belong to the team and are listed in
> section 9 as open.

Every statement carries one label:

| Label | Meaning |
|---|---|
| **[EXISTING]** | The API code in `backend/api/` already does this. It is covered by local tests with in-memory fakes. It is **not** verified on real AWS |
| **[PROPOSAL]** | Suggested worker behavior. It is not implemented and the team may change it |
| **[OPEN]** | A decision nobody has made yet. This document does not make it |

---

## 1. Where the worker sits

```
client -> API Gateway -> API Lambda -> DynamoDB (record) + SQS (one message) -> worker Lambda -> DynamoDB
```

- The API Lambda accepts a route, stores a capture record and sends one SQS message.
- The worker reads that message, checks and processes the route, and writes the final state to the
  same DynamoDB record.
- The client only ever talks to the API. It polls `GET /api/v1/captures/{captureId}`.

## 2. What the API already guarantees [EXISTING]

1. **One message per accepted capture.** Body (`schemaVersion` is `1`):

   ```json
   {
     "schemaVersion": 1,
     "captureId": "capture_<32 hex>",
     "playerId": "<cognito sub>",
     "route": { "encoding": "gzip+base64", "data": "<base64 text>" }
   }
   ```

   Maximum size 1 MiB. `route.data` is base64, then gzip, then JSON. `unpack_route` in
   `backend/api/inline_route_store.py` does this decoding and can be reused.
2. **`playerId` is trustworthy.** It comes only from the verified token claim `sub`, never from the
   request body or a header.
3. **`captureId` is derived** from the player and the `Idempotency-Key` (a SHA-256 based value), so one
   logical capture always has one record.
4. **Write order in the API:** create the record as `RECEIVED` -> send the message -> mark the record
   `PENDING`. `202` is returned only after the queue accepted the message.
5. **The `PENDING` mark is conditional** (`status = RECEIVED`). If the worker already moved the record
   on, the API does not overwrite the worker's progress.
6. **A message can arrive before the record is `PENDING`.** The message is sent before the mark. So the
   worker can read the record while it is still `RECEIVED`.
7. **Duplicate messages are possible.** If the send succeeded but marking `PENDING` failed, the API
   answers `503`, and a client retry with the same key sends the message again.
8. **`RECEIVED` is hidden.** A client asking for a capture in `RECEIVED` gets `404`. Once the worker
   moves it to `PROCESSING`, the client can see it.
9. **Statuses** used by the code: `RECEIVED` (internal), `PENDING`, `PROCESSING`, `SUCCEEDED`,
   `REJECTED`, `FAILED`.
10. **Only structure is validated.** The route has 4 to 10,000 samples, finite numbers in range, strictly
    increasing UTC timestamps. **Plausibility is not checked** (speed, jumps, GPS accuracy, loops).
    `INVALID_ROUTE` is reserved for the worker.
11. **The API changes a record only at the start** (create, then the `PENDING` mark). It never touches a
    record afterwards and sets no TTL.
12. **A capture is visible only to its owner.** The record carries `playerId`.
13. **Logging rule in the API:** no GPS data, claims or tokens are logged.

What the API does **not** have: any code that updates a record after `PENDING`. The worker's writes are
new code.

## 3. Proposed processing flow [PROPOSAL]

(The lead agreed to this as a starting point on 2026-11-27.)

1. Read the message. If it cannot be decoded, see section 7.
2. Read the record by `captureId` (strongly consistent) and check that `playerId` matches the message.
3. If the status is already final (`SUCCEEDED`, `REJECTED`, `FAILED`): do nothing and delete the message.
4. Otherwise claim the record: move it to `PROCESSING` with a conditional write (section 4).
5. Check plausibility, then calculate and store the territory result. (**[OPEN]**, section 9.)
6. Write the final status with a conditional write (section 5), then delete the message.

The worker never trusts anything in the route beyond what step 5 checks, and never logs GPS data.

## 4. State transitions and conditional writes [PROPOSAL]

Final states never change again.

| From | To | Condition on the write |
|---|---|---|
| `RECEIVED` or `PENDING` | `PROCESSING` | `status IN (RECEIVED, PENDING)` |
| `PROCESSING` (lease expired) | `PROCESSING` | `status = PROCESSING AND updatedAt < :leaseCutoff` (reclaim, section 6) |
| `PROCESSING` | `SUCCEEDED` or `REJECTED` | `status = PROCESSING` |
| any non-final | `FAILED` | `status IN (RECEIVED, PENDING, PROCESSING)` |
| final | anything | never. The condition fails, the worker deletes the message |

Every write also sets `updatedAt`. If a conditional write fails, the worker re-reads the record and
decides again. It must not retry blindly.

## 5. Idempotency [PROPOSAL]

- The unit of idempotency is `captureId`. Processing the same message twice must give the same final
  record.
- The final write is conditional on `status = PROCESSING`, so a second worker that finishes later
  cannot overwrite a result that is already final.
- The calculation should be deterministic for the same route. Whether it is depends on the territory
  logic, so this is **[OPEN]**.
- An optional attempt token (a random value written at the claim and checked at the final write) would
  stop a slow, reclaimed worker from finishing as if it still owned the record. It needs one extra
  attribute on the capture item, which changes the data model, so the worker owner decides. **[OPEN]**

## 6. Crash after `PROCESSING` (lead's question 1) [PROPOSAL]

**The problem.** The worker sets `PROCESSING` and then crashes or times out. SQS delivers the message
again after the visibility timeout. If the retry sees `PROCESSING` and gives up, the capture would be
stuck for ever.

**Proposed recovery: a lease based on `updatedAt`.**

1. Claiming a record sets `status = PROCESSING` and `updatedAt = now`. This is the lease start.
2. A retry that reads `PROCESSING` compares `updatedAt` with a **lease duration**:
   - **Lease expired** (`updatedAt` is older than the lease): reclaim with the conditional write in
     section 4 (`updatedAt < :leaseCutoff`) and process the capture again.
   - **Lease still valid**: another worker may still be running. Do **not** process and do **not** delete
     the message. Return it as failed so SQS makes it visible again later.
3. The lease duration must be **longer than the worker Lambda timeout**, so a working worker is never
   reclaimed. The queue's visibility timeout should be at least 6 times the worker timeout (AWS guidance
   for Lambda event sources). The numbers are the lead's decision. **[OPEN]**
4. Because the reclaim is a conditional write, two retries cannot both reclaim the same record.

**Limits of this proposal.**

- If a capture keeps crashing the worker, it is retried until `maxReceiveCount`, then goes to the DLQ
  (section 7). Reclaiming does not stop that loop by itself.
- A scheduled sweeper that looks for old `PROCESSING` records is another option. It needs a way to find
  them (a scan or an index), which the current table design does not have. **[OPEN]**

## 7. Failed messages and the DLQ (lead's question 2) [OPEN]

**Fact.** Moving a message to the DLQ does **not** change the DynamoDB record. A capture whose message
went to the DLQ stays in `PENDING` or `PROCESSING` and the client polls it for ever. [EXISTING behavior
of SQS and DynamoDB; nothing in the API or the worker updates the record today.]

This document does **not** decide how the record becomes `FAILED`. Options for the team:

| Option | How | Weak point |
|---|---|---|
| A. DLQ consumer | A small Lambda reads the DLQ and marks the record `FAILED` | One more Lambda to build and deploy |
| B. Worker on the last attempt | The worker checks the SQS receive count and writes `FAILED` before the final retry | Cannot help when the worker crashes or times out on that attempt |
| C. Sweeper | A scheduled job marks old non-final records `FAILED` | Needs a way to find them; extra infrastructure |
| D. Several of the above | For example B plus A as a safety net | More work |

Also open: what the worker does with a message it can never process (bad base64, bad gzip, bad JSON,
unknown `schemaVersion`). The API never produces such a message, so this is defensive. Possible rule: if
the `captureId` is readable, write `FAILED` and delete the message; otherwise let it go to the DLQ.

**Message handling summary** [PROPOSAL, except the DLQ outcome which is OPEN]:

| Situation | Message | Record |
|---|---|---|
| Final state already reached | Delete | Unchanged |
| Success | Delete | `SUCCEEDED` |
| Route fails plausibility (permanent) | Delete | `REJECTED` |
| Temporary error (DynamoDB, internal) | Keep, SQS retries | Unchanged or `PROCESSING` with lease |
| Lease still valid on another worker | Keep, SQS retries | Unchanged |
| Retries exhausted, message in the DLQ | In the DLQ | **[OPEN]** (options above) |

## 8. Batch size (lead's question 3)

**Lead's direction: batch size 1 for the MVP.** [PROPOSAL, agreed as the lean]

- One message per invocation. A success or failure applies to that one capture, so no partial batch
  reporting is needed.
- If the batch size is raised later, the function must report which messages failed
  (`ReportBatchItemFailures`), otherwise one failure retries the whole batch. That is a later change.
- This also keeps the lease from section 6 simple: one capture is claimed per invocation.

## 9. Pending team decisions [OPEN]

These are **not** decided by the API side. The API stores `result` and `error` as opaque maps and does not
interpret them.

1. **Final `result` shape** for `SUCCEEDED`: pending team decision. This includes the territory
   representation (polygon format, coordinates, area and its unit), how overlap with other players is
   resolved, and any score or XP.
2. **Final `error` shape** for `REJECTED` and `FAILED`: pending team decision. `INVALID_ROUTE` is reserved
   in the API contract. `docs/GAME_RULES.md` lists other codes (for example `CAPTURE_ALREADY_PROCESSED`);
   they have **not** been reconciled with `docs/API_CONTRACT.md` section 6.
3. **How `GET /api/v1/captures/{captureId}` shows `result` and `error`** to the client. Today the API
   returns `captureId`, `status`, `createdAt` and `updatedAt`. Adding the fields needs the shapes from 1
   and 2.
4. **Territory data model** and where territories are stored (see `docs/DATA_MODEL.md`).
5. **Plausibility rules** (maximum speed, jump distance, accuracy limit, minimum length, loop closing).
6. **Lease duration, worker timeout, queue visibility timeout, `maxReceiveCount`.**
7. **DLQ handling** (section 7) and **cleanup of records stuck in `RECEIVED`** (the API sets no TTL).
8. **Attempt token** (section 5).
9. **A way for clients to read territories.** The map design shows other players' areas. That needs a new
   API route, which is not part of the current MVP.

## 10. Not covered

- Any worker code, territory algorithm or game rule.
- Infrastructure for the worker (see `docs/INFRASTRUCTURE_REQUIREMENTS.md` for the API Lambda only).
- Alarms, dashboards, monitoring of the DLQ and any production security review.
