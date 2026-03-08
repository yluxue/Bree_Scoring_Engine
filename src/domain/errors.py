class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid state transition from '{from_state}' to '{to_state}'")

class DuplicateApplicationError(Exception):
    def __init__(self, original_application_id: str):
        self.original_application_id = original_application_id
        super().__init__(f"Duplicate application detected. Original ID: {original_application_id}")

class WebhookReplayError(Exception):
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Webhook replay detected for transaction ID: {transaction_id}")
