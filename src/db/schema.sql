CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    applicant_name TEXT NOT NULL,
    email TEXT NOT NULL,
    loan_amount INTEGER NOT NULL,
    status TEXT NOT NULL,
    score INTEGER,
    breakdown TEXT, -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_data (
    application_id TEXT PRIMARY KEY,
    stated_monthly_income INTEGER NOT NULL,
    employment_status TEXT NOT NULL,
    documented_monthly_income INTEGER,
    bank_ending_balance INTEGER,
    bank_has_overdrafts BOOLEAN,
    bank_has_consistent_deposits BOOLEAN,
    monthly_withdrawals INTEGER,
    monthly_deposits INTEGER,
    FOREIGN KEY(application_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL,
    event_type TEXT NOT NULL, -- e.g., 'status_change', 'webhook_attempt'
    details TEXT, -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(application_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS webhooks (
    transaction_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    status TEXT NOT NULL, -- 'success', 'failed'
    timestamp TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(application_id) REFERENCES applications(id)
);
