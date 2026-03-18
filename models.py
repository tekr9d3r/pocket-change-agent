from __future__ import annotations

import re
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# Strict Ethereum address: 0x + exactly 40 hex characters
_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

def _validate_eth_addresses(addresses: list[str]) -> list[str]:
    if not addresses:
        raise ValueError("At least one wallet address is required")
    if len(addresses) > 20:
        raise ValueError("Maximum 20 wallet addresses per request")
    for addr in addresses:
        if not _ETH_ADDRESS_RE.match(addr):
            raise ValueError(
                f"Invalid Ethereum address: {addr!r}. "
                "Must be 0x followed by exactly 40 hex characters."
            )
    return addresses


class AgentRegistration(BaseModel):
    agent_id: Annotated[str, Field(min_length=1, max_length=100)]
    wallet_addresses: list[str]

    @field_validator("wallet_addresses")
    @classmethod
    def validate_addresses(cls, addresses: list[str]) -> list[str]:
        return _validate_eth_addresses(addresses)


class AgentRequest(BaseModel):
    wallet_addresses: list[str]
    agent_context: Annotated[Optional[str], Field(default=None, max_length=500)]
    requesting_agent: Annotated[Optional[str], Field(default=None, max_length=100)]

    @field_validator("wallet_addresses")
    @classmethod
    def validate_addresses(cls, addresses: list[str]) -> list[str]:
        return _validate_eth_addresses(addresses)


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
    estimated_value_usd: float = 0.0
    risk_level: Literal["low", "medium", "high"] = "low"
    fee_model: str = "deposit_fee"
    fee_percentage: float = 0.025
    fee_amount_eth: str = "0.000000"
    fee_recipient: str = ""
    requires_signature: bool
    execution_steps: list[ExecutionStep]
    notes_for_agents: str
