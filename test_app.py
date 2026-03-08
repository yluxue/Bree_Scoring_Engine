import pytest
from fastapi.testclient import TestClient
import os
import json

# Setup env for testing so we don't mess up dev db
os.environ["DB_PATH"] = "test_bree.db"

# Now we import app which imports all routes which use DB_PATH if we configured it correctly.
# Oh wait, DB_PATH is hardcoded in repository.py. Let me fix that.
from src.main import app
from src.db.repository import init_db
import src.db.repository as repo

# Override DB path for tests
repo.DB_PATH = "test_bree.db"

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists("test_bree.db"):
        os.remove("test_bree.db")
    init_db()
    yield
    if os.path.exists("test_bree.db"):
        os.remove("test_bree.db")


# Scenarios from PDF:
# 1 Jane Doe $1,500 $5,000/mo Strong financials Auto-approve
# 2 Bob Smith $2,000 $1,400/mo Weak financials Auto-deny
# 3 Bob Smith $300 $1,400/mo Weak financials Flag for review
# 4 Jane Doe $4,500 $5,000/mo Strong financials Flag for review
# 5 Carol Tester $1,000 $8,000/mo No documents Flag for review
# 6 Dave Liar $2,000 $10,000/mo Doc shows $1,400/mo Auto-deny
# 7 Jane Doe $1,500 $5,000/mo Resubmit within 1 min Duplicate rejected
# 8 (webhook) — — Same txn_id sent twice Idempotent

SCENARIOS = [
  {
    "scenario": 1,
    "input": {
      "applicant_name": "Jane Doe",
      "email": "jane.doe@example.com",
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
  },
  {
    "scenario": 2,
    "input": {
      "applicant_name": "Bob Smith",
      "email": "bob.smith@example.com",
      "loan_amount": 2000,
      "stated_monthly_income": 1400,
      "employment_status": "self-employed",
      "documented_monthly_income": 1350,
      "bank_ending_balance": 150,
      "bank_has_overdrafts": True,
      "bank_has_consistent_deposits": False,
      "monthly_withdrawals": 1100,
      "monthly_deposits": 1350
    }
  },
  {
    "scenario": 3,
    "note": "Reuses Bob Smith's financial data with a smaller loan amount",
    "input": {
      "applicant_name": "Bob Smith",
      "email": "bob.smith@example.com",
      "loan_amount": 300,
      "stated_monthly_income": 1400,
      "employment_status": "self-employed",
      "documented_monthly_income": 1350,
      "bank_ending_balance": 150,
      "bank_has_overdrafts": True,
      "bank_has_consistent_deposits": False,
      "monthly_withdrawals": 1100,
      "monthly_deposits": 1350
    }
  },
  {
    "scenario": 4,
    "note": "Reuses Jane Doe's financial data with a larger loan amount",
    "input": {
      "applicant_name": "Jane Doe",
      "email": "jane.doe@example.com",
      "loan_amount": 4500,
      "stated_monthly_income": 5000,
      "employment_status": "employed",
      "documented_monthly_income": 4800,
      "bank_ending_balance": 3200,
      "bank_has_overdrafts": False,
      "bank_has_consistent_deposits": True,
      "monthly_withdrawals": 1200,
      "monthly_deposits": 4800
    }
  },
  {
    "scenario": 5,
    "input": {
      "applicant_name": "Carol Tester",
      "email": "carol.tester@example.com",
      "loan_amount": 1000,
      "stated_monthly_income": 8000,
      "employment_status": "employed"
    }
  },
  {
    "scenario": 6,
    "input": {
      "applicant_name": "Dave Liar",
      "email": "dave.liar@example.com",
      "loan_amount": 2000,
      "stated_monthly_income": 10000,
      "employment_status": "employed",
      "documented_monthly_income": 1400,
      "bank_ending_balance": 150,
      "bank_has_overdrafts": True,
      "bank_has_consistent_deposits": False,
      "monthly_withdrawals": 1100,
      "monthly_deposits": 1400
    }
  }
]


def test_scenario_1_auto_approve():
    response = client.post("/applications/", json=SCENARIOS[0]["input"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "disbursement_queued" # Auto-appoved translates directly to dispatcher queueing

def test_scenario_2_auto_deny():
    response = client.post("/applications/", json=SCENARIOS[1]["input"])
    assert response.status_code == 201
    assert response.json()["status"] == "denied"

def test_scenario_3_flag_for_review_small_loan():
    response = client.post("/applications/", json=SCENARIOS[2]["input"])
    assert response.status_code == 201
    assert response.json()["status"] == "flagged_for_review"

def test_scenario_4_flag_for_review_large_loan():
    response = client.post("/applications/", json=SCENARIOS[3]["input"])
    assert response.status_code == 201
    assert response.json()["status"] == "flagged_for_review"

def test_scenario_5_flag_for_review_no_docs():
    response = client.post("/applications/", json=SCENARIOS[4]["input"])
    assert response.status_code == 201
    assert response.json()["status"] == "flagged_for_review"

def test_scenario_6_auto_deny_liar():
    response = client.post("/applications/", json=SCENARIOS[5]["input"])
    assert response.status_code == 201
    assert response.json()["status"] == "denied"

def test_scenario_7_duplicate_rejected():
    # Submit first
    client.post("/applications/", json=SCENARIOS[0]["input"])
    # Submit second within 5 mins
    response = client.post("/applications/", json=SCENARIOS[0]["input"])
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data
    assert "original_application_id" in data["detail"]
    assert data["detail"]["error"] == "DuplicateApplicationError"

def test_scenario_8_webhook_idempotent():
    # Submit valid approved
    resp = client.post("/applications/", json=SCENARIOS[0]["input"])
    app_id = resp.json()["application_id"]

    txn_id = "txn_8_123"
    webhook_payload = {
        "application_id": app_id,
        "status": "success",
        "transaction_id": txn_id,
        "timestamp": "2026-01-15T10:30:00Z"
    }

    # First webhook
    w_resp_1 = client.post("/webhook/disbursement", json=webhook_payload)
    assert w_resp_1.status_code == 200

    # Second webhook with same txn
    w_resp_2 = client.post("/webhook/disbursement", json=webhook_payload)
    assert w_resp_2.status_code == 200
    assert w_resp_2.json()["message"] == "Idempotent response for existing transaction"


def test_admin_review():
    # Test review of flagged to partially approved
    resp = client.post("/applications/", json=SCENARIOS[2]["input"]) # flagged
    app_id = resp.json()["application_id"]
    
    auth = ("admin", "secret")
    review_resp = client.post(
        f"/admin/applications/{app_id}/review",
        auth=auth,
        json={
            "status": "partially_approved",
            "note": "Lower risk amount",
            "approved_loan_amount": 200
        }
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["result"] == "success"
    # When partially approved, it should also queue disbursement automatically
    assert review_resp.json()["new_status"] == "disbursement_queued"
