from src.config import SCORING_WEIGHTS, DECISION_THRESHOLDS, INCOME_TOLERANCE_MULTIPLIER
from src.domain.models import LoanApplicationInput, ApplicationStatus, ApplicationScoreResult, EmploymentStatus

def calculate_score(app: LoanApplicationInput) -> ApplicationScoreResult:
    score = 0
    breakdown = {}

    # 1. Income Verification (30%)
    # My interpretation: documented >= stated * 0.90
    if app.documented_monthly_income is not None:
        required_minimum = app.stated_monthly_income * INCOME_TOLERANCE_MULTIPLIER
        if app.documented_monthly_income >= required_minimum:
            score += int(100 * SCORING_WEIGHTS.income_verification)
            breakdown["income_verification"] = 30
        else:
            breakdown["income_verification"] = 0
    else:
        breakdown["income_verification"] = 0

    # 2. Income Level (25%)
    # My interpretation: Using documented_monthly_income as the basis for conservative scoring.
    if app.documented_monthly_income is not None and app.documented_monthly_income >= 3 * app.loan_amount:
        score += int(100 * SCORING_WEIGHTS.income_level)
        breakdown["income_level"] = 25
    else:
        breakdown["income_level"] = 0

    # 3. Account Stability (20%)
    stability_score = 0
    if app.bank_ending_balance is not None and app.bank_ending_balance > 0:
        stability_score += int((100 * SCORING_WEIGHTS.account_stability) / 3)
    if app.bank_has_overdrafts is False:
        stability_score += int((100 * SCORING_WEIGHTS.account_stability) / 3)
    if app.bank_has_consistent_deposits is True:
        stability_score += int((100 * SCORING_WEIGHTS.account_stability) / 3)
    
    # Ensure no rounding issues exceed 20
    stability_score = min(20, stability_score)
    score += stability_score
    breakdown["account_stability"] = stability_score

    # 4. Employment Status (15%)
    # Employed > self-employed > unemployed
    if app.employment_status == EmploymentStatus.EMPLOYED:
        score += int(100 * SCORING_WEIGHTS.employment_status)
        breakdown["employment_status"] = 15
    elif app.employment_status == EmploymentStatus.SELF_EMPLOYED:
        self_employed_points = int(100 * SCORING_WEIGHTS.employment_status * 0.5)
        score += self_employed_points
        breakdown["employment_status"] = self_employed_points
    else:
        breakdown["employment_status"] = 0

    # 5. Debt-to-Income (10%)
    dti_score = 0
    if app.monthly_deposits and app.monthly_deposits > 0 and app.monthly_withdrawals is not None:
        ratio = app.monthly_withdrawals / app.monthly_deposits
        if ratio <= 0.3:
            dti_score = 10
        elif ratio <= 0.5:
            dti_score = 5
        elif ratio <= 0.7:
            dti_score = 3
        elif ratio <= 0.9:
            dti_score = 1
    score += dti_score
    breakdown["debt_to_income"] = dti_score

    score = min(100, score)

    # Determine status
    if score >= DECISION_THRESHOLDS.auto_approve_min:
        status = ApplicationStatus.APPROVED
    elif score < DECISION_THRESHOLDS.auto_deny_max + 1: # < 50
        status = ApplicationStatus.DENIED
    else:
        status = ApplicationStatus.FLAGGED_FOR_REVIEW

    # Flag for review if there are missing infos in the input (Carol Tester test case)
    has_no_docs = (
        app.documented_monthly_income is None
        and app.bank_ending_balance is None
    )
    if has_no_docs:
        status = ApplicationStatus.FLAGGED_FOR_REVIEW

    return ApplicationScoreResult(
        score=score,
        status=status,
        breakdown=breakdown
    )
