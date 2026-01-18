from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class EntryType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    REVERSAL = "REVERSAL"


class RewardStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PAID = "PAID"
    REVERSED = "REVERSED"
    EXPIRED = "EXPIRED"


class CreateRewardRequest(BaseModel):
    idempotency_key: str = Field(..., description="Unique key to prevent duplicates")
    referrer_user_id: UUID
    referred_user_id: UUID
    reward_definition_id: Optional[UUID] = None
    amount: Optional[Decimal] = None
    currency: str = Field(default="INR")
    description: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "idempotency_key": "referral-123-signup-2024",
            "referrer_user_id": "550e8400-e29b-41d4-a716-446655440000",
            "referred_user_id": "660e8400-e29b-41d4-a716-446655440001",
            "amount": 500.00,
            "currency": "INR"
        }
    })


class ReverseRewardRequest(BaseModel):
    reason: str = Field(..., description="Reason for reversal")
    performed_by: Optional[str] = None


class ConfirmRewardRequest(BaseModel):
    performed_by: Optional[str] = None


class LedgerEntry(BaseModel):
    id: UUID
    user_id: UUID
    entry_type: EntryType
    amount: Decimal
    currency: str = "INR"
    balance_after: Decimal
    reward_event_id: Optional[UUID] = None
    reference_entry_id: Optional[UUID] = None
    idempotency_key: str
    description: str
    created_at: datetime
    metadata: dict = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)


class RewardEvent(BaseModel):
    id: UUID
    idempotency_key: str
    reward_definition_id: Optional[UUID] = None
    referrer_user_id: UUID
    referred_user_id: UUID
    status: RewardStatus
    amount: Decimal
    currency: str = "INR"
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    reversed_at: Optional[datetime] = None
    created_by: Optional[str] = None
    reversal_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    def can_reverse(self) -> bool:
        return self.status in (RewardStatus.PENDING, RewardStatus.CONFIRMED)
    
    def can_confirm(self) -> bool:
        return self.status == RewardStatus.PENDING


class UserBalance(BaseModel):
    user_id: UUID
    currency: str
    current_balance: Decimal
    total_entries: int
    last_transaction_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class LedgerHistoryResponse(BaseModel):
    user_id: UUID
    entries: list[LedgerEntry]
    total_count: int
    current_balance: Decimal


class RewardResponse(BaseModel):
    reward: RewardEvent
    ledger_entry: Optional[LedgerEntry] = None
    message: str
