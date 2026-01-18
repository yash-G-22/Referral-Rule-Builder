CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE entry_type AS ENUM ('CREDIT', 'DEBIT', 'REVERSAL');
CREATE TYPE reward_status AS ENUM ('PENDING', 'CONFIRMED', 'PAID', 'REVERSED', 'EXPIRED');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    is_paid_user BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE reward_definitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    reward_type VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE reward_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    reward_definition_id UUID REFERENCES reward_definitions(id),
    referrer_user_id UUID NOT NULL REFERENCES users(id),
    referred_user_id UUID NOT NULL REFERENCES users(id),
    status reward_status NOT NULL DEFAULT 'PENDING',
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    paid_at TIMESTAMP WITH TIME ZONE,
    reversed_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255),
    reversal_reason TEXT,
    CONSTRAINT valid_participants CHECK (referrer_user_id != referred_user_id)
);

CREATE INDEX idx_reward_events_referrer ON reward_events(referrer_user_id);
CREATE INDEX idx_reward_events_referred ON reward_events(referred_user_id);
CREATE INDEX idx_reward_events_status ON reward_events(status);
CREATE INDEX idx_reward_events_idempotency ON reward_events(idempotency_key);

-- Immutable ledger entries table
CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    entry_type entry_type NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    balance_after DECIMAL(15, 2) NOT NULL,
    reward_event_id UUID REFERENCES reward_events(id),
    reference_entry_id UUID REFERENCES ledger_entries(id),
    idempotency_key VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_ledger_user ON ledger_entries(user_id);
CREATE INDEX idx_ledger_created ON ledger_entries(created_at);
CREATE INDEX idx_ledger_reward ON ledger_entries(reward_event_id);
CREATE INDEX idx_ledger_reference ON ledger_entries(reference_entry_id);
CREATE UNIQUE INDEX idx_ledger_idempotency ON ledger_entries(idempotency_key, entry_type);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    performed_by VARCHAR(255),
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    request_id UUID,
    ip_address INET
);

CREATE INDEX idx_audit_table ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_time ON audit_log(performed_at);

-- Prevent ledger modifications
CREATE OR REPLACE FUNCTION prevent_ledger_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Ledger entries are immutable';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_ledger_immutability
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION prevent_ledger_modification();

CREATE OR REPLACE VIEW user_balances AS
SELECT 
    user_id,
    currency,
    SUM(amount) AS current_balance,
    COUNT(*) AS total_entries,
    MAX(created_at) AS last_transaction_at
FROM ledger_entries
GROUP BY user_id, currency;

-- Seed data
INSERT INTO reward_definitions (id, name, description, reward_type, amount, currency) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Referral Signup Bonus', 'Reward for successful referral signup', 'VOUCHER', 100.00, 'INR'),
    ('22222222-2222-2222-2222-222222222222', 'Subscription Bonus', 'Reward when referred user subscribes', 'VOUCHER', 500.00, 'INR'),
    ('33333333-3333-3333-3333-333333333333', 'Premium Referral Bonus', 'Premium reward for paid user referrals', 'CASH', 1000.00, 'INR');
