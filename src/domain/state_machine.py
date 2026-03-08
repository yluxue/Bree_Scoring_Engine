from src.domain.models import ApplicationStatus
from src.domain.errors import InvalidStateTransitionError

# Define allowed transitions
ALLOWED_TRANSITIONS = {
    ApplicationStatus.SUBMITTED: {ApplicationStatus.PROCESSING},
    ApplicationStatus.PROCESSING: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.DENIED,
        ApplicationStatus.FLAGGED_FOR_REVIEW
    },
    ApplicationStatus.FLAGGED_FOR_REVIEW: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.PARTIALLY_APPROVED,
        ApplicationStatus.DENIED
    },
    ApplicationStatus.APPROVED: {ApplicationStatus.DISBURSEMENT_QUEUED},
    ApplicationStatus.PARTIALLY_APPROVED: {ApplicationStatus.DISBURSEMENT_QUEUED},
    ApplicationStatus.DISBURSEMENT_QUEUED: {
        ApplicationStatus.DISBURSED,
        ApplicationStatus.DISBURSEMENT_FAILED
    },
    ApplicationStatus.DISBURSEMENT_FAILED: {
        ApplicationStatus.DISBURSEMENT_QUEUED,
        ApplicationStatus.FLAGGED_FOR_REVIEW
    },
    ApplicationStatus.DENIED: set(),
    ApplicationStatus.DISBURSED: set(),
}

class StateMachine:
    @staticmethod
    def transition(current_state: ApplicationStatus, next_state: ApplicationStatus) -> ApplicationStatus:
        """
        Validates state transitions and returns next_state if valid.
        Raises InvalidStateTransitionError if invalid.
        """
        valid_next_states = ALLOWED_TRANSITIONS.get(current_state, set())
        
        if next_state not in valid_next_states:
            raise InvalidStateTransitionError(current_state.value, next_state.value)
            
        return next_state
