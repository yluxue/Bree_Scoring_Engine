from enum import Enum
from pydantic import BaseModel

class ScoringWeights(BaseModel):
    income_verification: float = 0.30
    income_level: float = 0.25
    account_stability: float = 0.20
    employment_status: float = 0.15
    debt_to_income: float = 0.10

class DecisionThresholds(BaseModel):
    auto_approve_min: int = 75
    auto_deny_max: int = 49 # Score < 50

# Global Config Object
SCORING_WEIGHTS = ScoringWeights()
DECISION_THRESHOLDS = DecisionThresholds()

# Income verification tolerance (Documented Income must be at least 90% of Stated Income)
INCOME_TOLERANCE_MULTIPLIER = 0.90
