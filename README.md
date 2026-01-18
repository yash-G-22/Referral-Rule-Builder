# Referral Management System

A comprehensive referral management system with two core components:
1. **Financial Ledger System** - Immutable ledger for tracking referral rewards
2. **Rule-Based Flow Builder** - Visual tool for defining referral logic

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (optional - uses in-memory storage for demo)

### Installation
```bash
cd referral-system
pip install -r requirements.txt
```

### Run the API Server
```bash
uvicorn ledger.api:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

### Open the Flow Builder
Open `flow-builder/index.html` in your browser.

### Run Tests
```bash
pytest ledger/tests/ -v
```

---

## Part 1: Financial Ledger System

### Data Model (PostgreSQL)

**Why SQL over NoSQL?**
- **ACID compliance** - Critical for financial transactions
- **Referential integrity** - Enforced relationships between entities
- **Strong typing** - Prevents invalid data entry
- **Transaction support** - Atomic multi-table operations

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `reward_definitions` | Reward templates |
| `reward_events` | Reward lifecycle tracking |
| `ledger_entries` | **Immutable** transaction log |
| `audit_log` | Compliance audit trail |

### How Correctness is Ensured

#### 1. Immutability
```sql
-- Ledger entries cannot be modified after creation
CREATE TRIGGER enforce_ledger_immutability
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION prevent_ledger_modification();
```

Reversals create **new entries** with negative amounts rather than modifying existing ones.

#### 2. Idempotency
```sql
-- Unique constraint prevents duplicate rewards
idempotency_key VARCHAR(255) NOT NULL UNIQUE
```

The same request with the same `idempotency_key` returns the existing result without creating duplicates.

#### 3. Atomic Operations
All state changes (reward + ledger entry) happen in a single database transaction:
```python
# Atomically creates both:
# 1. RewardEvent in PENDING state
# 2. LedgerEntry with credit amount
```

#### 4. Derived Balance
Balance is **calculated from ledger entries**, never stored separately:
```python
def get_balance(user_id):
    return sum(entry.amount for entry in ledger_entries)
```

This ensures balance is always consistent with the transaction history.

---

### Reversals & Adjustments

**Reversal Flow:**
1. Find original reward and ledger entry
2. Validate state (`PENDING` or `CONFIRMED` only)
3. Create new `REVERSAL` entry with negative amount
4. Update reward status to `REVERSED`
5. Net effect on balance: original - reversal = 0

```
Original Entry:  +₹500 (CREDIT)
Reversal Entry:  -₹500 (REVERSAL) ← references original
Net Balance:      ₹0
```

**Why this approach?**
- Original entry preserved for audit
- Clear trail of what happened
- No data mutation = no corruption risk

---

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rewards` | Create reward (credit) |
| POST | `/rewards/{id}/confirm` | Confirm pending reward |
| POST | `/rewards/{id}/reverse` | Reverse reward |
| GET | `/users/{id}/balance` | Get user balance |
| GET | `/users/{id}/ledger` | Get transaction history |

---

## Part 2: Rule-Based Flow Builder

### Rule Format (JSON AST)

**Why JSON?**
- Human-readable and debuggable
- Easy to serialize/store
- Natural for UI state management
- Validates with JSON Schema

### Example Rule
```json
{
  "id": "rule-premium-referral",
  "name": "Premium Referral Reward",
  "trigger": "subscription_started",
  "conditions": {
    "operator": "AND",
    "conditions": [
      {"field": "referrer.is_paid_user", "operator": "equals", "value": true},
      {"field": "referred.subscription_plan", "operator": "equals", "value": "premium"}
    ]
  },
  "actions": [
    {
      "type": "credit_reward",
      "params": {"amount": 500, "currency": "INR", "reward_type": "voucher"}
    }
  ]
}
```

### Rule Engine Features
- Nested condition groups (AND/OR)
- Multiple condition operators (equals, greater_than, contains, etc.)
- Pluggable action handlers
- Priority-based rule execution

### Visual Flow Builder
- Drag-and-drop node creation
- Bezier curve connections
- Property editing panel
- Export to JSON
- **Bonus:** Natural language to rule generation

---

## 🎁 LLM Integration

The system includes an LLM parser that converts natural language to rules:

**Input:**
> "When a paid user refers someone who subscribes to premium, reward 500 rupees voucher"

**Output:** Structured JSON rule with conditions and actions.

Supports:
- Groq API

---

## What's Completed ✅

### Part 1: Financial Ledger
- [x] PostgreSQL schema with immutability enforcement
- [x] Pydantic models for type safety
- [x] Credit reward flow (full implementation)
- [x] Reverse reward flow (full implementation)
- [x] Confirm reward flow
- [x] Balance calculation
- [x] FastAPI REST API with Swagger docs
- [x] Unit tests for all flows

### Part 2: Rule Builder
- [x] JSON AST rule format with schema
- [x] Rule engine with condition evaluation
- [x] Visual flow builder UI
- [x] Drag-and-drop nodes
- [x] Node connections
- [x] Export to JSON
- [x] LLM parser (bonus)
- [x] Natural language generation (bonus)

---

## Project Structure

```
referral-system/
├── README.md
├── requirements.txt
├── database/
│   └── schema.sql          # PostgreSQL schema
├── ledger/
│   ├── __init__.py
│   ├── models.py           # Pydantic models
│   ├── service.py          # Business logic
│   ├── api.py              # FastAPI endpoints
│   └── tests/
│       └── test_ledger.py  # Unit tests
├── rules/
│   ├── __init__.py
│   ├── rule_schema.json    # JSON Schema
│   ├── rule_engine.py      # Evaluation engine
│   └── llm_parser.py       # NL to JSON
└── flow-builder/
    ├── index.html          # UI structure
    ├── style.css           # Dark mode styling
    └── flow-builder.js     # Canvas logic
```

---

## AI Usage Disclosure

This project was developed using Claude Code (Anthropic) as a pair programming assistant:

- **Architecture Design**: Discussed tradeoffs between SQL/NoSQL, immutable ledger patterns
- **Code Generation**: Generated boilerplate, models, and repetitive code
- **Problem Solving**: Debugged issues with connection rendering and state management
- **Documentation**: Assisted with README structure and explanations

Human contributions focused on:
- System design decisions
- Code review and refinement
- Testing and validation
- Final polish and documentation

---

## License

MIT
