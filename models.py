from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, field_validator


class AgentRequest(BaseModel):
    wallet_addresses: list[str]
    agent_context: Optional[str] = None
    requesting_agent: Optional[str] = None
    max_eth_threshold_usd: float = 30.0

    @field_validator("wallet_addresses")
    @classmethod
    def validate_addresses(cls, addresses: list[str]) -> list[str]:
        for addr in addresses:
            if not addr.startswith("0x") or len(addr) != 42:
                raise ValueError(
                    f"Invalid Ethereum address: {addr!r}. "
                    "Must start with '0x' and be 42 characters long."
                )
        return addresses


class ExecutionStep(BaseModel):
    step: int
    action: str
    contract: Optional[str] = None
    calldata: Optional[str] = None
    value_eth: Optional[str] = None
    notes: Optional[str] = None


class PocketChangeResponse(BaseModel):
    agent: str = "PocketChange"
    chain: str = "ethereum"
    wallets_analyzed: list[str]
    pocket_change_wallets: list[str]
    recommended_action: Literal["stake", "wait", "none", "insufficient_information"]
    decision_reasoning: str
    protocol: str = "lido"
    estimated_value_usd: float
    risk_level: Literal["low", "medium", "high"]
    fee_model: str = "deposit_fee"
    fee_percentage: float = 0.25
    fee_amount_eth: str
    fee_recipient: str
    requires_signature: bool
    execution_steps: list[ExecutionStep]
    notes_for_agents: str
