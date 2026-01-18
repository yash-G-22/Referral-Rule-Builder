from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.models import (
    CreateRewardRequest, ReverseRewardRequest, ConfirmRewardRequest,
    RewardResponse, UserBalance, LedgerHistoryResponse, RewardEvent,
)
from ledger.service import (
    LedgerService, LedgerServiceError, RewardNotFoundError,
    InvalidStateTransitionError, IdempotencyConflictError,
)
from uuid import UUID

app = FastAPI(
    title="Referral Ledger API",
    description="Financial ledger system for referral rewards",
    version="1.0.0",
    root_path="/api"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ledger_service = LedgerService()


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "referral-ledger"}


@app.post("/rewards", response_model=RewardResponse, status_code=status.HTTP_201_CREATED)
def create_reward(request: CreateRewardRequest):
    try:
        return ledger_service.credit_reward(request)
    except IdempotencyConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except LedgerServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/rewards/{reward_id}", response_model=RewardEvent)
def get_reward(reward_id: UUID):
    try:
        return ledger_service.get_reward(reward_id)
    except RewardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reward {reward_id} not found")


@app.post("/rewards/{reward_id}/confirm", response_model=RewardResponse)
def confirm_reward(reward_id: UUID, request: ConfirmRewardRequest):
    try:
        return ledger_service.confirm_reward(reward_id, request)
    except RewardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reward {reward_id} not found")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/rewards/{reward_id}/reverse", response_model=RewardResponse)
def reverse_reward(reward_id: UUID, request: ReverseRewardRequest):
    try:
        return ledger_service.reverse_reward(reward_id, request)
    except RewardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reward {reward_id} not found")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/users/{user_id}/balance", response_model=UserBalance)
def get_user_balance(user_id: UUID, currency: str = "INR"):
    return ledger_service.get_balance(user_id, currency)


@app.get("/users/{user_id}/ledger", response_model=LedgerHistoryResponse)
def get_user_ledger(user_id: UUID, limit: int = 50, offset: int = 0):
    return ledger_service.get_ledger_history(user_id, limit, offset)


handler = Mangum(app)
