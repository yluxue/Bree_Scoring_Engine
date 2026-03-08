import secrets
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from src.domain.models import ApplicationStatus, AdminReviewInput
from src.domain.state_machine import StateMachine
from src.domain.errors import InvalidStateTransitionError
from src.db.repository import Repository

router = APIRouter(prefix="/admin/applications", tags=["admin"])
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "secret")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.get("/")
def list_applications(status: str = None, user: str = Depends(authenticate)):
    if status:
        try:
            status_enum = ApplicationStatus(status)
            apps = Repository.list_applications_by_status(status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    else:
    
        raise HTTPException(status_code=400, detail="Must provide status filter")
        
    return {"applications": apps}

@router.get("/{app_id}")
def get_application_detail(app_id: str, user: str = Depends(authenticate)):
    app = Repository.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@router.post("/{app_id}/review")
def review_application(app_id: str, review_input: AdminReviewInput, user: str = Depends(authenticate)):
    app = Repository.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    current_status = ApplicationStatus(app['status'])
    
    try:
        # Validate transition using StateMachine
        next_state = StateMachine.transition(current_status, review_input.status)
        
        # Apply transition
        Repository.update_application_status(
            app_id=app_id,
            old_status=current_status,
            new_status=next_state,
            note=review_input.note,
            approved_loan_amount=review_input.approved_loan_amount
        )
        
        # If successfully reviewed to APPROVED or PARTIALLY_APPROVED, queue disbursement
        if next_state in [ApplicationStatus.APPROVED, ApplicationStatus.PARTIALLY_APPROVED]:
            next_next_state = StateMachine.transition(next_state, ApplicationStatus.DISBURSEMENT_QUEUED)
            Repository.update_application_status(
                app_id=app_id,
                old_status=next_state,
                new_status=next_next_state,
                note="Admin approved, queuing disbursement"
            )
            
        return {"result": "success", "new_status": next_state if next_state not in [ApplicationStatus.APPROVED, ApplicationStatus.PARTIALLY_APPROVED] else ApplicationStatus.DISBURSEMENT_QUEUED}
            
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail={"error": "InvalidStateTransitionError", "message": str(e)})

