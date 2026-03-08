from enum import Enum
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    DENIED = "denied"
    FLAGGED_FOR_REVIEW = "flagged_for_review"
    DISBURSEMENT_QUEUED = "disbursement_queued"
    DISBURSED = "disbursed"
    DISBURSEMENT_FAILED = "disbursement_failed"

class EmploymentStatus(str, Enum):
    EMPLOYED = "employed"
    SELF_EMPLOYED = "self-employed"
    UNEMPLOYED = "unemployed"

class LoanApplicationInput(BaseModel):
    applicant_name: str
    email: str
    loan_amount: int
    stated_monthly_income: int
    employment_status: EmploymentStatus
    documented_monthly_income: Optional[int] = None
    bank_ending_balance: Optional[int] = None
    bank_has_overdrafts: Optional[bool] = None
    bank_has_consistent_deposits: Optional[bool] = None
    monthly_withdrawals: Optional[int] = None
    monthly_deposits: Optional[int] = None

class ApplicationScoreResult(BaseModel):
    score: int
    status: ApplicationStatus
    breakdown: dict

class AdminReviewInput(BaseModel):
    status: ApplicationStatus
    note: str
    approved_loan_amount: Optional[int] = None

class WebhookDisbursementInput(BaseModel):
    application_id: str
    status: str
    transaction_id: str
    timestamp: str
