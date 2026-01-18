"""
Unit Tests for the Ledger Service

Tests cover:
1. Credit reward flow
2. Idempotency (duplicate prevention)
3. Reversal flow
4. Balance calculation
5. State transitions
"""

import pytest
from decimal import Decimal
from uuid import UUID

from ledger.models import (
    CreateRewardRequest,
    ReverseRewardRequest,
    ConfirmRewardRequest,
    RewardStatus,
    EntryType,
)
from ledger.service import (
    LedgerService,
    RewardNotFoundError,
    InvalidStateTransitionError,
)


# Test constants
REFERRER_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
REFERRED_ID = UUID("660e8400-e29b-41d4-a716-446655440001")
REWARD_DEF_ID = UUID("22222222-2222-2222-2222-222222222222")


class TestCreditRewardFlow:
    """Tests for the credit reward flow."""
    
    def test_create_reward_success(self):
        """Test successful reward creation."""
        service = LedgerService()
        
        request = CreateRewardRequest(
            idempotency_key="test-reward-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            reward_definition_id=REWARD_DEF_ID,
            amount=Decimal("500.00"),
            currency="INR",
            description="Test reward for signup"
        )
        
        response = service.credit_reward(request)
        
        # Verify reward created
        assert response.reward is not None
        assert response.reward.status == RewardStatus.PENDING
        assert response.reward.amount == Decimal("500.00")
        assert response.reward.referrer_user_id == REFERRER_ID
        assert response.reward.referred_user_id == REFERRED_ID
        
        # Verify ledger entry created
        assert response.ledger_entry is not None
        assert response.ledger_entry.entry_type == EntryType.CREDIT
        assert response.ledger_entry.amount == Decimal("500.00")
        assert response.ledger_entry.balance_after == Decimal("500.00")
    
    def test_idempotency_returns_existing(self):
        """Test that same idempotency key returns existing reward."""
        service = LedgerService()
        
        request = CreateRewardRequest(
            idempotency_key="idempotent-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            reward_definition_id=REWARD_DEF_ID,
            amount=Decimal("100.00"),
        )
        
        # Create first time
        response1 = service.credit_reward(request)
        reward_id = response1.reward.id
        
        # Create second time with same key
        response2 = service.credit_reward(request)
        
        # Should return same reward
        assert response2.reward.id == reward_id
        assert "already exists" in response2.message.lower()
        
        # Balance should not double
        balance = service.get_balance(REFERRER_ID)
        assert balance.current_balance == Decimal("100.00")
    
    def test_multiple_rewards_accumulate(self):
        """Test that multiple rewards with different keys accumulate."""
        service = LedgerService()
        
        # Create first reward
        response1 = service.credit_reward(CreateRewardRequest(
            idempotency_key="multi-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("100.00"),
        ))
        
        # Create second reward
        response2 = service.credit_reward(CreateRewardRequest(
            idempotency_key="multi-test-002",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("200.00"),
        ))
        
        # Balance should be sum
        balance = service.get_balance(REFERRER_ID)
        assert balance.current_balance == Decimal("300.00")
        assert balance.total_entries == 2


class TestReverseRewardFlow:
    """Tests for the reverse reward flow."""
    
    def test_reverse_pending_reward(self):
        """Test reversing a pending reward."""
        service = LedgerService()
        
        # Create reward
        create_response = service.credit_reward(CreateRewardRequest(
            idempotency_key="reversal-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("500.00"),
        ))
        
        reward_id = create_response.reward.id
        
        # Verify balance before reversal
        balance_before = service.get_balance(REFERRER_ID)
        assert balance_before.current_balance == Decimal("500.00")
        
        # Reverse the reward
        reverse_response = service.reverse_reward(
            reward_id,
            ReverseRewardRequest(
                reason="User cancelled subscription",
                performed_by="admin@test.com"
            )
        )
        
        # Verify reward status
        assert reverse_response.reward.status == RewardStatus.REVERSED
        assert reverse_response.reward.reversal_reason == "User cancelled subscription"
        
        # Verify reversal entry
        assert reverse_response.ledger_entry is not None
        assert reverse_response.ledger_entry.entry_type == EntryType.REVERSAL
        assert reverse_response.ledger_entry.amount == Decimal("-500.00")
        
        # Verify balance is now zero
        balance_after = service.get_balance(REFERRER_ID)
        assert balance_after.current_balance == Decimal("0.00")
    
    def test_reverse_confirmed_reward(self):
        """Test reversing a confirmed reward."""
        service = LedgerService()
        
        # Create and confirm reward
        create_response = service.credit_reward(CreateRewardRequest(
            idempotency_key="reversal-confirmed-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("300.00"),
        ))
        
        reward_id = create_response.reward.id
        
        # Confirm the reward
        service.confirm_reward(reward_id, ConfirmRewardRequest())
        
        # Reverse should still work
        reverse_response = service.reverse_reward(
            reward_id,
            ReverseRewardRequest(reason="Fraud detected")
        )
        
        assert reverse_response.reward.status == RewardStatus.REVERSED
        
        # Balance should be zero
        balance = service.get_balance(REFERRER_ID)
        assert balance.current_balance == Decimal("0.00")
    
    def test_cannot_reverse_already_reversed(self):
        """Test that reversing an already reversed reward fails."""
        service = LedgerService()
        
        # Create and reverse
        create_response = service.credit_reward(CreateRewardRequest(
            idempotency_key="double-reverse-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("100.00"),
        ))
        
        reward_id = create_response.reward.id
        service.reverse_reward(reward_id, ReverseRewardRequest(reason="First reversal"))
        
        # Try to reverse again
        with pytest.raises(InvalidStateTransitionError):
            service.reverse_reward(reward_id, ReverseRewardRequest(reason="Second reversal"))
    
    def test_reverse_nonexistent_reward_fails(self):
        """Test that reversing a non-existent reward fails."""
        service = LedgerService()
        
        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        
        with pytest.raises(RewardNotFoundError):
            service.reverse_reward(fake_id, ReverseRewardRequest(reason="Test"))


class TestConfirmRewardFlow:
    """Tests for the confirm reward flow."""
    
    def test_confirm_pending_reward(self):
        """Test confirming a pending reward."""
        service = LedgerService()
        
        # Create reward
        create_response = service.credit_reward(CreateRewardRequest(
            idempotency_key="confirm-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("250.00"),
        ))
        
        reward_id = create_response.reward.id
        
        # Confirm
        confirm_response = service.confirm_reward(
            reward_id, 
            ConfirmRewardRequest(performed_by="system")
        )
        
        assert confirm_response.reward.status == RewardStatus.CONFIRMED
        assert confirm_response.reward.confirmed_at is not None
    
    def test_cannot_confirm_reversed_reward(self):
        """Test that confirming a reversed reward fails."""
        service = LedgerService()
        
        # Create and reverse
        create_response = service.credit_reward(CreateRewardRequest(
            idempotency_key="confirm-reversed-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("100.00"),
        ))
        
        reward_id = create_response.reward.id
        service.reverse_reward(reward_id, ReverseRewardRequest(reason="Test"))
        
        # Try to confirm
        with pytest.raises(InvalidStateTransitionError):
            service.confirm_reward(reward_id, ConfirmRewardRequest())


class TestBalanceCalculation:
    """Tests for balance calculation."""
    
    def test_balance_derived_from_entries(self):
        """Test that balance is correctly calculated from entries."""
        service = LedgerService()
        
        # Create multiple rewards
        service.credit_reward(CreateRewardRequest(
            idempotency_key="balance-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("100.00"),
        ))
        
        service.credit_reward(CreateRewardRequest(
            idempotency_key="balance-test-002",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("250.00"),
        ))
        
        # Reverse one
        response = service.credit_reward(CreateRewardRequest(
            idempotency_key="balance-test-003",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("50.00"),
        ))
        service.reverse_reward(response.reward.id, ReverseRewardRequest(reason="Test"))
        
        # Check balance: 100 + 250 + 50 - 50 = 350
        balance = service.get_balance(REFERRER_ID)
        assert balance.current_balance == Decimal("350.00")
        assert balance.total_entries == 4  # 3 credits + 1 reversal
    
    def test_ledger_history(self):
        """Test ledger history retrieval."""
        service = LedgerService()
        
        # Create some entries
        service.credit_reward(CreateRewardRequest(
            idempotency_key="history-test-001",
            referrer_user_id=REFERRER_ID,
            referred_user_id=REFERRED_ID,
            amount=Decimal("100.00"),
        ))
        
        # Get history
        history = service.get_ledger_history(REFERRER_ID)
        
        assert history.user_id == REFERRER_ID
        assert len(history.entries) >= 1
        assert history.total_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
