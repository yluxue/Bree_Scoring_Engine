from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.domain.models import LoanApplicationInput, ApplicationStatus
from src.domain.scoring_engine import calculate_score
from src.domain.errors import DuplicateApplicationError
from src.db.repository import Repository

router = APIRouter(prefix="/applications", tags=["applications"])

class SubmitApplicationResponse(BaseModel):
    application_id: str
    status: str

@router.post("/", response_model=SubmitApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_application(app_input: LoanApplicationInput):
    # 1. Check for duplicates (same email + loan amount within 5 mins)
    recent_app = Repository.get_recent_application(app_input.email, app_input.loan_amount, minutes=5)
    if recent_app:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "DuplicateApplicationError", "original_application_id": recent_app["id"]}
        )
    
    # 2. Score application
    score_result = calculate_score(app_input)
    
    # 3. Save application
    app_id = Repository.create_application(
        app_input=app_input,
        status=score_result.status,
        score=score_result.score,
        breakdown=score_result.breakdown
    )
    
    
    
    if score_result.status == ApplicationStatus.APPROVED:
        # Queue disbursement (using state machine)
        from src.domain.state_machine import StateMachine
        next_state = StateMachine.transition(ApplicationStatus.APPROVED, ApplicationStatus.DISBURSEMENT_QUEUED)
        
        Repository.update_application_status(
            app_id=app_id,
            old_status=ApplicationStatus.APPROVED,
            new_status=next_state,
            note="Auto-approved and queuing disbursement"
        )
        return SubmitApplicationResponse(application_id=app_id, status=next_state)
    
    return SubmitApplicationResponse(application_id=app_id, status=score_result.status)
