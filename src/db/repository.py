import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List
from src.domain.models import ApplicationStatus, LoanApplicationInput

DB_PATH = "bree_scoring.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with open("src/db/schema.sql", "r") as f:
        schema = f.read()
    
    # Use execute script for multiple statements
    conn.executescript(schema)
    conn.commit()
    conn.close()

class Repository:
    @staticmethod
    def get_recent_application(email: str, loan_amount: int, minutes: int = 5) -> Optional[dict]:
        """Checks if there's an application with the same email and loan amount within the last `minutes`."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT id FROM applications 
                WHERE email = ? AND loan_amount = ? 
                AND datetime(created_at) >= datetime('now', '-' || ? || ' minutes')
            """
            cur.execute(query, (email, loan_amount, minutes))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    @staticmethod
    def create_application(app_input: LoanApplicationInput, status: ApplicationStatus, score: int, breakdown: dict) -> str:
        conn = get_connection()
        app_id = str(uuid.uuid4())
        try:
            conn.execute("BEGIN TRANSACTION")
            cur = conn.cursor()
            
            # Insert root application
            cur.execute("""
                INSERT INTO applications (id, applicant_name, email, loan_amount, status, score, breakdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (app_id, app_input.applicant_name, app_input.email, app_input.loan_amount, status.value, score, json.dumps(breakdown)))
            
            # Insert application data
            cur.execute("""
                INSERT INTO application_data (
                    application_id, stated_monthly_income, employment_status, documented_monthly_income,
                    bank_ending_balance, bank_has_overdrafts, bank_has_consistent_deposits,
                    monthly_withdrawals, monthly_deposits
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id, app_input.stated_monthly_income, app_input.employment_status.value,
                app_input.documented_monthly_income, app_input.bank_ending_balance,
                app_input.bank_has_overdrafts, app_input.bank_has_consistent_deposits,
                app_input.monthly_withdrawals, app_input.monthly_deposits
            ))
            
            # Record initial state transition in audit log
            cur.execute("""
                INSERT INTO audit_logs (application_id, event_type, details)
                VALUES (?, ?, ?)
            """, (app_id, 'status_change', json.dumps({"from": None, "to": status.value})))
            
            conn.execute("COMMIT")
            return app_id
        except Exception as e:
            conn.execute("ROLLBACK")
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_application(app_id: str) -> Optional[dict]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.*, d.* FROM applications a
                LEFT JOIN application_data d ON a.id = d.application_id
                WHERE a.id = ?
            """, (app_id,))
            row = cur.fetchone()
            if row:
                result = dict(row)
                if result['breakdown']:
                    result['breakdown'] = json.loads(result['breakdown'])
                return result
            return None
        finally:
            conn.close()

    @staticmethod
    def list_applications_by_status(status: ApplicationStatus) -> List[dict]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM applications WHERE status = ?", (status.value,))
            rows = cur.fetchall()
            results = []
            for row in rows:
                r = dict(row)
                if r['breakdown']:
                    r['breakdown'] = json.loads(r['breakdown'])
                results.append(r)
            return results
        finally:
            conn.close()
            
    @staticmethod
    def update_application_status(app_id: str, old_status: str, new_status: str, note: str = None, 
                                 approved_loan_amount: int = None, transaction: sqlite3.Connection = None) -> None:
        conn = transaction if transaction else get_connection()
        own_transaction = transaction is None
        try:
            if own_transaction:
                conn.execute("BEGIN TRANSACTION")
            
            cur = conn.cursor()
            
            update_query = "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP"
            params = [new_status]
            
            if approved_loan_amount is not None:
                update_query += ", loan_amount = ?"
                params.append(approved_loan_amount)
                
            update_query += " WHERE id = ?"
            params.append(app_id)
            
            cur.execute(update_query, tuple(params))
            
            details = {"from": old_status, "to": new_status}
            if note:
                details['note'] = note
            if approved_loan_amount is not None:
                details['approved_loan_amount'] = approved_loan_amount
                
            cur.execute("""
                INSERT INTO audit_logs (application_id, event_type, details)
                VALUES (?, ?, ?)
            """, (app_id, 'status_change', json.dumps(details)))
            
            if own_transaction:
                conn.execute("COMMIT")
        except Exception as e:
            if own_transaction:
                conn.execute("ROLLBACK")
            raise e
        finally:
            if own_transaction:
                conn.close()

    @staticmethod
    def get_webhook(transaction_id: str) -> Optional[dict]:
        """Used to check idempotency."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM webhooks WHERE transaction_id = ?", (transaction_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    @staticmethod
    def count_failed_webhooks(app_id: str) -> int:
        """Count how many failed webhooks have been processed for an application."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM webhooks WHERE application_id = ? AND status = 'failed'", (app_id,))
            return cur.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def record_webhook_attempt(app_id: str, transaction_id: str, status: str, timestamp: str) -> None:
        conn = get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")
            cur = conn.cursor()
            
            # Record webhook - ignores if exists for idempotency, but audit log still fires below if we reach here
            # Wait, if transaction_id exists it'll fail primary key constraint. 
            # We should manage the distinct audit log requirement.
            
            # The spec says:
            # "Finance team says each retry must be logged as a separate audit event with a unique retry ID"
            # Idempotency vs Audit Trail: We log every POST payload as an audit event 'webhook_attempt', 
            # even if the transaction_id was previously seen (a true repeat doesn't update the core webhooks table)
            # We'll use INSERT OR IGNORE for the idempotency on the main webhooks table
            
            cur.execute("""
                INSERT OR IGNORE INTO webhooks (transaction_id, application_id, status, timestamp)
                VALUES (?, ?, ?, ?)
            """, (transaction_id, app_id, status, timestamp))
            
            # Log the unique retry event regardless
            cur.execute("""
                INSERT INTO audit_logs (application_id, event_type, details)
                VALUES (?, ?, ?)
            """, (app_id, 'webhook_attempt', json.dumps({
                "transaction_id": transaction_id,
                "status": status,
                "timestamp": timestamp
            })))
            
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
