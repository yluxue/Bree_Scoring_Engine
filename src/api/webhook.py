from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.domain.models import WebhookDisbursementInput, ApplicationStatus
from src.domain.state_machine import StateMachine
from src.domain.errors import InvalidStateTransitionError
from src.db.repository import Repository

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/disbursement")
def handle_disbursement_webhook(webhook: WebhookDisbursementInput):
    # Retrieve application
    app = Repository.get_application(webhook.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    current_status = ApplicationStatus(app["status"])

    # Idempotency check
    existing_txn = Repository.get_webhook(webhook.transaction_id)
    if existing_txn:
        # Log the retry attempt to audit logs 
        Repository.record_webhook_attempt(
            app_id=webhook.application_id,
            transaction_id=webhook.transaction_id,
            status=webhook.status,
            timestamp=webhook.timestamp
        )
        return {"status": "ok", "message": "Idempotent response for existing transaction"}

    # log the webhook attempt 
    Repository.record_webhook_attempt(
        app_id=webhook.application_id,
        transaction_id=webhook.transaction_id,
        status=webhook.status,
        timestamp=webhook.timestamp
    )
    
    # Process valid webhook
    if webhook.status == "success":
        target_state = ApplicationStatus.DISBURSED
    elif webhook.status == "failed":
        target_state = ApplicationStatus.DISBURSEMENT_FAILED
    else:
        raise HTTPException(status_code=400, detail="Invalid status field in webhook")

    try:
        next_state = StateMachine.transition(current_status, target_state)
        Repository.update_application_status(
            app_id=webhook.application_id,
            old_status=current_status,
            new_status=next_state,
            note=f"Webhook {webhook.status}"
        )
        
        # If the status was FAILED, it's retryable. So we transition it immediately back to QUEUED
        # or FLAGGED_FOR_REVIEW if max retries reached.
        if next_state == ApplicationStatus.DISBURSEMENT_FAILED:
            failed_count = Repository.count_failed_webhooks(webhook.application_id)
            # 1 initial attempt + 3 retries = 4 allowed failures before escalating
            if failed_count < 4:
                # Requeue it
                next_next_state = StateMachine.transition(next_state, ApplicationStatus.DISBURSEMENT_QUEUED)
                Repository.update_application_status(
                    app_id=webhook.application_id, 
                    old_status=next_state, 
                    new_status=next_next_state,
                    note=f"Auto-requeue following failure (Retry {failed_count}/3)"
                )
            else:
                # Escalate to manual review
                next_next_state = StateMachine.transition(next_state, ApplicationStatus.FLAGGED_FOR_REVIEW)
                Repository.update_application_status(
                    app_id=webhook.application_id, 
                    old_status=next_state, 
                    new_status=next_next_state,
                    note="Max retries reached, escalated to manual review"
                )

        return {"status": "ok"}
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail={"error": "InvalidStateTransitionError", "message": str(e)})
