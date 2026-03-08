# Bree Backend Scoring Engine

This is the backend orchestration and scoring logic for the AI-Powered Loan Application Processor.
It includes the Application state management, scoring engine, webhook flows (including idempotency and audit logs), and an Admin API.

## Design Decisions

### Income Tolerance Ambiguity
**Spec**: "10% tolerance"
**Implementation**: `documented_monthly_income >= stated_monthly_income * 0.90`
*Reasoning*: In lending, it is generally acceptable to be conservative and *understate* income. We flag or deny if the user *overstated* their income by more than 10% (meaning their actual documented income is lower than 90% of what they claimed).

### Retry vs Audit Trail Conflict
**Spec**: "Finance says each retry must be logged as a separate audit event, but Product says webhooks must be idempotent."
**Implementation**: Webhooks are idempotent on the state-machine and `webhooks` table via `transaction_id`. If `txn_123` is sent twice, the application state doesn't change, and `200 OK` is returned. *However*, we write an `audit_logs` record row with `event_type = 'webhook_attempt'` for **every** incoming webhook request. This allows Finance to see 3 distinct webhook attempts, while the application's actual state transitions only once.

### "No Documents" Edge Case
**Spec**: Carol Tester has 'null' for all doc/bank variables, and expected outcome is "Flag for Review".
**Implementation**: Explicit check in `scoring_engine.py`. If documents and banking data are missing (`None`), but the user still generated some valid score through stated data (e.g. they score exactly 40 which normally means `Auto-deny`), we override the threshold and force `FLAGGED_FOR_REVIEW` so a human can manually resolve the missing files.

## Setup Instructions

Tested on Python 3.11+.

1. Create a virtual environment and install requirements:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the tests:
   ```bash
   pytest test_app.py -v
   ```

3. Start the server (SQLite DB `bree_scoring.db` initializes automatically):
   ```bash
   uvicorn src.main:app --reload
   ```

4. Run the webhook simulator in another terminal (needs server running):
   ```bash
   # arg = success/failure/invalid/Idempotency for different scenarios
   python3 simulate_disbursement.py <arg>
   ```

## Tradeoffs

- **Synchronous vs Event-Driven**: In a high-throughput system (10k+/day), state transitions (like queueing disbursement after approval) would be asynchronous. Here, it is executed synchronously for simplicity.
- **SQLite Concurrency**: SQLite is file-locked. I used simple transactions `BEGIN/COMMIT`. At high scale, we'd use Postgres with connection pooling.
- **Webhook Retry Logic**: A production system would have a background worker polling the `webhooks` table or queue for `failed` events and retrying automatically. The simulator manually executes these retries to demonstrate idempotency and audit trails.
