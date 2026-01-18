from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from .models import (
    EntryType,
    RewardStatus,
    LedgerEntry,
    RewardEvent,
    UserBalance,
    CreateRewardRequest,
    ReverseRewardRequest,
    ConfirmRewardRequest,
    RewardResponse,
    LedgerHistoryResponse,
)


class LedgerServiceError(Exception):
    pass


class IdempotencyConflictError(LedgerServiceError):
    pass


class RewardNotFoundError(LedgerServiceError):
    pass


class InvalidStateTransitionError(LedgerServiceError):
    pass


class InMemoryStorage:
    def __init__(self):
        self.users: dict[UUID, dict] = {}
        self.reward_events: dict[UUID, dict] = {}
        self.ledger_entries: dict[UUID, dict] = {}
        self.reward_definitions: dict[UUID, dict] = {}
        self.idempotency_index: dict[str, UUID] = {}
        self._seed_data()
    
    def _seed_data(self):
        user1_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        user2_id = UUID("660e8400-e29b-41d4-a716-446655440001")
        
        self.users[user1_id] = {
            "id": user1_id, "email": "referrer@example.com",
            "name": "John Referrer", "is_paid_user": True,
            "created_at": datetime.now(timezone.utc)
        }
        self.users[user2_id] = {
            "id": user2_id, "email": "referred@example.com",
            "name": "Jane Referred", "is_paid_user": False,
            "created_at": datetime.now(timezone.utc)
        }
        
        self.reward_definitions[UUID("11111111-1111-1111-1111-111111111111")] = {
            "id": UUID("11111111-1111-1111-1111-111111111111"),
            "name": "Referral Signup Bonus", "reward_type": "VOUCHER",
            "amount": Decimal("100.00"), "currency": "INR"
        }
        self.reward_definitions[UUID("22222222-2222-2222-2222-222222222222")] = {
            "id": UUID("22222222-2222-2222-2222-222222222222"),
            "name": "Subscription Bonus", "reward_type": "VOUCHER",
            "amount": Decimal("500.00"), "currency": "INR"
        }


class LedgerService:
    def __init__(self, storage: Optional[InMemoryStorage] = None):
        self.storage = storage or InMemoryStorage()
    
    def credit_reward(self, request: CreateRewardRequest) -> RewardResponse:
        existing_reward = self._check_idempotency(request.idempotency_key)
        if existing_reward:
            return RewardResponse(
                reward=existing_reward,
                ledger_entry=self._get_ledger_entry_for_reward(existing_reward.id),
                message="Reward already exists (idempotent return)"
            )
        
        amount = request.amount
        if amount is None and request.reward_definition_id:
            reward_def = self.storage.reward_definitions.get(request.reward_definition_id)
            if reward_def:
                amount = reward_def["amount"]
        
        if amount is None:
            amount = Decimal("0.00")
        
        current_balance = self.get_balance(request.referrer_user_id, request.currency)
        new_balance = current_balance.current_balance + amount
        
        now = datetime.now(timezone.utc)
        reward_id = uuid4()
        
        reward_data = {
            "id": reward_id,
            "idempotency_key": request.idempotency_key,
            "reward_definition_id": request.reward_definition_id,
            "referrer_user_id": request.referrer_user_id,
            "referred_user_id": request.referred_user_id,
            "status": RewardStatus.PENDING,
            "amount": amount,
            "currency": request.currency,
            "created_at": now,
            "confirmed_at": None, "paid_at": None,
            "reversed_at": None, "created_by": None, "reversal_reason": None,
        }
        
        entry_id = uuid4()
        entry_data = {
            "id": entry_id,
            "user_id": request.referrer_user_id,
            "entry_type": EntryType.CREDIT,
            "amount": amount,
            "currency": request.currency,
            "balance_after": new_balance,
            "reward_event_id": reward_id,
            "reference_entry_id": None,
            "idempotency_key": request.idempotency_key,
            "description": request.description or f"Referral reward credit for {request.referred_user_id}",
            "created_at": now,
            "metadata": {
                "referred_user_id": str(request.referred_user_id),
                "reward_definition_id": str(request.reward_definition_id) if request.reward_definition_id else None,
            }
        }
        
        self.storage.reward_events[reward_id] = reward_data
        self.storage.ledger_entries[entry_id] = entry_data
        self.storage.idempotency_index[request.idempotency_key] = reward_id
        
        return RewardResponse(
            reward=RewardEvent(**reward_data),
            ledger_entry=LedgerEntry(**entry_data),
            message="Reward created successfully"
        )
    
    def confirm_reward(self, reward_id: UUID, request: ConfirmRewardRequest) -> RewardResponse:
        reward_data = self.storage.reward_events.get(reward_id)
        if not reward_data:
            raise RewardNotFoundError(f"Reward {reward_id} not found")
        
        reward = RewardEvent(**reward_data)
        if not reward.can_confirm():
            raise InvalidStateTransitionError(f"Cannot confirm reward in {reward.status} state")
        
        reward_data["status"] = RewardStatus.CONFIRMED
        reward_data["confirmed_at"] = datetime.now(timezone.utc)
        self.storage.reward_events[reward_id] = reward_data
        
        return RewardResponse(
            reward=RewardEvent(**reward_data),
            ledger_entry=self._get_ledger_entry_for_reward(reward_id),
            message="Reward confirmed successfully"
        )
    
    def reverse_reward(self, reward_id: UUID, request: ReverseRewardRequest) -> RewardResponse:
        reward_data = self.storage.reward_events.get(reward_id)
        if not reward_data:
            raise RewardNotFoundError(f"Reward {reward_id} not found")
        
        reward = RewardEvent(**reward_data)
        if not reward.can_reverse():
            raise InvalidStateTransitionError(
                f"Cannot reverse reward in {reward.status} state. Only PENDING or CONFIRMED rewards can be reversed."
            )
        
        original_entry = self._get_ledger_entry_for_reward(reward_id)
        if not original_entry:
            raise LedgerServiceError(f"Original ledger entry not found for reward {reward_id}")
        
        current_balance = self.get_balance(reward.referrer_user_id, reward.currency)
        reversal_amount = -original_entry.amount
        new_balance = current_balance.current_balance + reversal_amount
        
        now = datetime.now(timezone.utc)
        reversal_entry_id = uuid4()
        
        reversal_entry_data = {
            "id": reversal_entry_id,
            "user_id": reward.referrer_user_id,
            "entry_type": EntryType.REVERSAL,
            "amount": reversal_amount,
            "currency": reward.currency,
            "balance_after": new_balance,
            "reward_event_id": reward_id,
            "reference_entry_id": original_entry.id,
            "idempotency_key": f"{reward.idempotency_key}:reversal",
            "description": f"Reversal: {request.reason}",
            "created_at": now,
            "metadata": {
                "reversal_reason": request.reason,
                "performed_by": request.performed_by,
                "original_entry_id": str(original_entry.id),
                "original_amount": str(original_entry.amount),
            }
        }
        
        reward_data["status"] = RewardStatus.REVERSED
        reward_data["reversed_at"] = now
        reward_data["reversal_reason"] = request.reason
        
        self.storage.ledger_entries[reversal_entry_id] = reversal_entry_data
        self.storage.reward_events[reward_id] = reward_data
        
        return RewardResponse(
            reward=RewardEvent(**reward_data),
            ledger_entry=LedgerEntry(**reversal_entry_data),
            message="Reward reversed successfully"
        )
    
    def get_balance(self, user_id: UUID, currency: str = "INR") -> UserBalance:
        entries = [
            e for e in self.storage.ledger_entries.values()
            if e["user_id"] == user_id and e["currency"] == currency
        ]
        
        total_balance = sum(e["amount"] for e in entries)
        last_entry = max(entries, key=lambda e: e["created_at"]) if entries else None
        
        return UserBalance(
            user_id=user_id,
            currency=currency,
            current_balance=Decimal(str(total_balance)),
            total_entries=len(entries),
            last_transaction_at=last_entry["created_at"] if last_entry else None
        )
    
    def get_ledger_history(self, user_id: UUID, limit: int = 50, offset: int = 0) -> LedgerHistoryResponse:
        all_entries = [
            LedgerEntry(**e) for e in self.storage.ledger_entries.values()
            if e["user_id"] == user_id
        ]
        all_entries.sort(key=lambda e: e.created_at, reverse=True)
        paginated = all_entries[offset:offset + limit]
        balance = self.get_balance(user_id)
        
        return LedgerHistoryResponse(
            user_id=user_id,
            entries=paginated,
            total_count=len(all_entries),
            current_balance=balance.current_balance
        )
    
    def get_reward(self, reward_id: UUID) -> RewardEvent:
        reward_data = self.storage.reward_events.get(reward_id)
        if not reward_data:
            raise RewardNotFoundError(f"Reward {reward_id} not found")
        return RewardEvent(**reward_data)
    
    def _check_idempotency(self, idempotency_key: str) -> Optional[RewardEvent]:
        reward_id = self.storage.idempotency_index.get(idempotency_key)
        if reward_id:
            reward_data = self.storage.reward_events.get(reward_id)
            if reward_data:
                return RewardEvent(**reward_data)
        return None
    
    def _get_ledger_entry_for_reward(self, reward_id: UUID) -> Optional[LedgerEntry]:
        for entry in self.storage.ledger_entries.values():
            if entry["reward_event_id"] == reward_id and entry["entry_type"] == EntryType.CREDIT:
                return LedgerEntry(**entry)
        return None
