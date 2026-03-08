import sys
import httpx
import uuid
import datetime
import sqlite3
import json

BASE_URL = "http://localhost:8000"

def send_webhook(app_id: str, status: str, txn_id: str):
    timestamp = datetime.datetime.now().isoformat() + "Z"
    payload = {
        "application_id": app_id,
        "status": status,
        "transaction_id": txn_id,
        "timestamp": timestamp
    }
    
    print(f"\nSending webhook for app {app_id}: {status} with transaction_id: {txn_id}")
    try:
        response = httpx.post(f"{BASE_URL}/webhook/disbursement", json=payload)
        print(f"Response: {response.status_code}")
        print(f"Body: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def show_audit_trail(app_id: str):
    print("\n--- Audit Trail from Database ---")
    try:
        conn = sqlite3.connect("bree_scoring.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT event_type, details, created_at FROM audit_logs WHERE application_id = ? ORDER BY id ASC", (app_id,))
        rows = cur.fetchall()
        for i, row in enumerate(rows, 1):
            print(f"{i}. [{row['created_at']}] {row['event_type']} -> {row['details']}")
        conn.close()
    except Exception as e:
        print(f"Could not read database: {e}")

def submit_application() -> str:
    print("\n--- 1. Submitting New Application ---")
    payload = {
        "applicant_name": "Jane Simulator",
        "email": f"jane.sim.{uuid.uuid4().hex[:6]}@example.com",
        "loan_amount": 1500,
        "stated_monthly_income": 5000,
        "employment_status": "employed",
        "documented_monthly_income": 4800,
        "bank_ending_balance": 3200,
        "bank_has_overdrafts": False,
        "bank_has_consistent_deposits": True,
        "monthly_withdrawals": 1200,
        "monthly_deposits": 4800
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/applications/", json=payload)
        response.raise_for_status()
        app_id = response.json()["application_id"]
        print(f"✅ Successfully created application: {app_id}")
        print(f"   Initial Status: {response.json()['status']}")
        return app_id
    except Exception as e:
        print(f"❌ Failed to create application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simulate_disbursement.py <mode>")
        print("Available modes: 'success', 'failure', 'idempotency', 'invalid'")
        sys.exit(1)
        
    mode = sys.argv[1].lower()
    print(f"--- Webhook Simulator ({mode} mode) ---")
    
    # Auto-generate application first!
    app_id = submit_application()
    
    if mode == "success":
        print("\n--- 2. [Happy Path: Normal Success Webhook] ---")
        success_txn = f"txn_succ_{uuid.uuid4().hex[:8]}"
        send_webhook(app_id, "success", success_txn)
        
    elif mode == "failure":
        print("\n--- 2. [Failure Path: Webhook Fails, triggers auto-requeue & escalation] ---")
        for attempt in range(1, 6):
            txn_id = f"txn_fail_{uuid.uuid4().hex[:8]}"
            if attempt == 5:
                print(f"\n[Attempt {attempt} - Expecting Rejection because App is now FLAGGED_FOR_REVIEW]")
            elif attempt == 4:
                print(f"\n[Attempt {attempt} - Max Retries Reached! Expecting Escalation to FLAGGED_FOR_REVIEW]")
            else:
                print(f"\n[Attempt {attempt} - Expecting Auto-Requeue]")
            send_webhook(app_id, "failed", txn_id)
        
    elif mode == "idempotency":
        print("\n--- 2. [Idempotency Path: Replaying exact same webhook] ---")
        shared_txn = f"txn_succ_{uuid.uuid4().hex[:8]}"
        send_webhook(app_id, "success", shared_txn)
        print("\n[Sending EXACT SAME transaction_id again...]")
        send_webhook(app_id, "success", shared_txn)
        
    elif mode == "invalid":
        print("\n--- 2. [Invalid State Path: Forcing an Invalid Transition] ---")
        # First we successfully disburse it
        print("   -> Moving app to 'disbursed' state first...")
        success_txn = f"txn_succ_{uuid.uuid4().hex[:8]}"
        send_webhook(app_id, "success", success_txn)
        
        # Now we try to fail it, which is illegal from 'disbursed' -> 'disbursement_failed'
        print("\n   -> Attempting to send a 'failed' webhook on an already disbursed app...")
        invalid_txn = f"txn_fail_{uuid.uuid4().hex[:8]}"
        send_webhook(app_id, "failed", invalid_txn)
        
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
        
    # Show audit trail
    show_audit_trail(app_id)
    
    print("\nDone simulating webhooks.")
