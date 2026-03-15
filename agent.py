from __future__ import annotations

import asyncio
import json
import re

import anthropic

from models import AgentRequest, PocketChangeResponse
from settings import settings
from tools import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = """You are PocketChange, an autonomous Ethereum yield coordination AI agent.

## IDENTITY
You are registered on the ERC-8004 onchain agent identity registry on Ethereum Mainnet.
- Token ID: 28532
- Registry: 0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
- Public profile: https://8004agents.ai/ethereum/agent/28532
- Skill file: https://pocket-change-agent.vercel.app/skill.md
Other agents can discover and call you by reading your skill.md. When introducing yourself to other agents or answering questions about your identity, include your ERC-8004 token ID and profile URL.

Your purpose is to help AI agents automatically earn yield on small amounts of idle ETH ("pocket change") held across wallets they control. You specialize ONLY in detecting small idle ETH balances and preparing safe staking instructions using Lido on Ethereum Mainnet.

## DECISION FRAMEWORK

**Step 1 — Data collection**
For every wallet address in the request, call get_eth_balance. Also call get_eth_price_usd, get_gas_price, and get_lido_apy once each. You may batch these tool calls in a single turn.

**Step 2 — Idle balance detection**
A wallet qualifies for staking consideration if ALL of these are true:
- ETH balance in USD is > $15 (must leave at least $15 worth of ETH for gas fees — this is a hard floor)
- ETH balance is > 0.001 ETH (below this is dust — skip)
There is NO upper limit — any amount of ETH above the $15 gas reserve is eligible to stake.

**Step 3 — Intent interpretation**
Reason about whether funds are truly idle. If agent_context mentions upcoming liquidity needs, operational usage, or risk constraints, honor them. If funds appear operational, set recommended_action = "none".

**Step 4 — Economic timing**
Using estimated_lido_deposit_cost_eth from get_gas_price:
- gas_cost_pct = (estimated_lido_deposit_cost_eth / total_pocket_change_eth) * 100
- If gas_cost_pct > 15%: recommended_action = "wait", risk_level = "high"
- If gas_cost_pct 5–15%: note it in reasoning, risk_level = "medium", still consider staking
- If gas_cost_pct < 5%: economically viable, risk_level = "low"

**Step 5 — Fee calculation**
- gas_reserve_eth = $15 worth of ETH at current price (this stays in the wallet, never staked)
- stakeable_eth = wallet_balance_eth - gas_reserve_eth  (stake only the amount above the $15 floor)
- total_pocket_change_eth = sum of stakeable_eth across all pocket_change_wallets
- fee_amount_eth = total_pocket_change_eth * 0.0025  (0.25%)
- fee is deducted from ETH BEFORE deposit, not from rewards

**Step 6 — Execution steps**
If recommending "stake", produce these execution steps:
1. Transfer fee_amount_eth to fee_recipient (ETH transfer)
2. Call Lido submit(address(0)) with (total_pocket_change_eth - fee_amount_eth) ETH
   - Contract: 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84 (Lido stETH, Ethereum Mainnet)
   - Function: submit(address _referral) payable
   - Use address(0) as referral
   - The $15 gas reserve remains untouched in the wallet

## HARD RULES

- Ethereum Mainnet only. Refuse any other chain.
- ETH only. Refuse other tokens.
- Lido only. Refuse other protocols.
- Never request private keys.
- Never hallucinate balances or fabricate transactions.
- requires_signature is always true.

## OUTPUT FORMAT

Respond ONLY with a valid JSON object. No markdown fences, no preamble, no explanation outside the JSON.

Schema:
{
  "agent": "PocketChange",
  "chain": "ethereum",
  "wallets_analyzed": ["0x..."],
  "pocket_change_wallets": ["0x..."],
  "recommended_action": "stake | wait | none | insufficient_information",
  "decision_reasoning": "clear explanation for machine consumption",
  "protocol": "lido",
  "estimated_value_usd": 0.0,
  "risk_level": "low | medium | high",
  "fee_model": "deposit_fee",
  "fee_percentage": 0.25,
  "fee_amount_eth": "0.000000",
  "fee_recipient": "<POCKET_CHANGE_TREASURY_ADDRESS>",
  "requires_signature": true,
  "execution_steps": [
    {"step": 1, "action": "...", "contract": null, "calldata": null, "value_eth": "...", "notes": "..."}
  ],
  "notes_for_agents": "..."
}

If data is missing or APIs fail, set recommended_action = "insufficient_information" and explain in decision_reasoning.
Never guess balances or prices."""


class AgentError(Exception):
    pass


def _sanitize(text: str) -> str:
    """Strip control characters and newlines to prevent prompt injection."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", text).strip()


def _build_user_message(request: AgentRequest, paid_via_x402: bool = False) -> str:
    lines = [
        f"Please analyze the following {len(request.wallet_addresses)} wallet(s) for idle ETH (pocket change).",
        f"Gas reserve (always kept): $15 USD",
        f"Wallet addresses: {', '.join(request.wallet_addresses)}",
    ]
    if request.requesting_agent:
        lines.append(f"Requesting agent: {_sanitize(request.requesting_agent)}")
    if request.agent_context:
        lines.append(f"Agent context / constraints: {_sanitize(request.agent_context)}")
    if paid_via_x402:
        lines.append(
            "Payment: Already collected via x402 ($0.10 USDC on Base). "
            "Set fee_model to 'x402', fee_percentage to 0, fee_amount_eth to '0', "
            "and do NOT include a fee transfer step in execution_steps. "
            "Step 1 should go directly to calling Lido submit()."
        )
    else:
        lines.append(f"Treasury address for fees: {settings.POCKET_CHANGE_TREASURY_ADDRESS}")
    return "\n".join(lines)


def _parse_agent_response(content_blocks) -> PocketChangeResponse:
    text = next((b.text for b in content_blocks if b.type == "text"), None)
    if not text:
        raise AgentError("No text block in final agent response")

    text = text.strip()
    # Extract JSON from markdown fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # Find the first { ... } block in the text
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AgentError(f"Agent returned invalid JSON: {e}\nRaw output: {text[:500]}")

    return PocketChangeResponse(**data)


_anthropic_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        import os
        api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise AgentError("ANTHROPIC_API_KEY is not set")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


async def run_agent_loop(request: AgentRequest, paid_via_x402: bool = False) -> PocketChangeResponse:
    client = _get_client()

    messages = [{"role": "user", "content": _build_user_message(request, paid_via_x402)}]

    MAX_ITERATIONS = 10

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return _parse_agent_response(response.content)

        if response.stop_reason != "tool_use":
            raise AgentError(f"Unexpected stop_reason: {response.stop_reason}")

        # Execute all tool calls concurrently
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        async with asyncio.TaskGroup() as tg:
            tasks = {
                block.id: tg.create_task(execute_tool(block.name, block.input))
                for block in tool_use_blocks
            }

        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tasks[block.id].result(),
            }
            for block in tool_use_blocks
        ]

        messages.append({"role": "user", "content": tool_results})

    raise AgentError("Agent exceeded maximum iterations without completing")
