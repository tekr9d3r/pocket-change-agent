# PocketChange Agent

An autonomous Ethereum yield coordination AI agent that detects idle ETH balances and prepares staking instructions via Lido.

Built for agent-to-agent interaction — PocketChange reasons about wallets, evaluates economic conditions, and produces deterministic machine-readable staking instructions. It never holds keys or executes transactions.

---

## What It Does

PocketChange scans Ethereum wallets for "pocket change" — small idle ETH balances between **$3 and $30 USD** — and recommends staking them through Lido to earn yield.

For each wallet it:

1. Fetches the real ETH balance (Etherscan)
2. Gets the current ETH/USD price (CoinGecko)
3. Evaluates current gas prices and estimates Lido deposit cost (Etherscan)
4. Fetches the current Lido staking APY
5. Reasons about whether funds are truly idle
6. Evaluates whether staking is economically rational given gas costs
7. Returns a structured JSON response with a recommendation and execution steps

---

## Pocket Change Definition

A wallet qualifies as pocket change if:

- ETH balance in USD is **≤ $30** (configurable)
- ETH balance in USD is **> $3** (hard floor — always kept for gas fees)
- ETH balance is **> 0.001 ETH** (dust threshold)

The $3 gas reserve is never staked. Only the amount above this floor is eligible.

---

## Decision Logic

| Condition | Action |
|-----------|--------|
| Gas cost > 15% of balance | `wait` — economically inefficient |
| Gas cost 5–15% of balance | `stake` with medium risk noted |
| Gas cost < 5% of balance | `stake` — economically viable |
| Funds appear operational | `none` — do not stake |
| Data unavailable | `insufficient_information` |

---

## Fee Model

PocketChange charges a **0.25% coordination fee** per staking deposit.

- Fee is calculated on the stakeable ETH (balance minus $3 gas reserve)
- Fee is deducted **before** the Lido deposit, not from rewards
- Fee is sent to the PocketChange treasury address
- PocketChange never custodies funds

**Example:** Wallet has 0.008 ETH ($20). Gas reserve = $3 worth of ETH. Stakeable = $17 worth. Fee = 0.25% of stakeable ETH.

---

## Protocol & Chain

| Parameter | Value |
|-----------|-------|
| Chain | Ethereum Mainnet only |
| Asset | ETH only |
| Protocol | Lido |
| Action | stake ETH → receive stETH |
| Lido contract | `0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84` |

Any request involving other chains, tokens, or protocols is refused.

---

## Output Schema

Every response returns structured JSON:

```json
{
  "agent": "PocketChange",
  "chain": "ethereum",
  "wallets_analyzed": ["0x..."],
  "pocket_change_wallets": ["0x..."],
  "recommended_action": "stake | wait | none | insufficient_information",
  "decision_reasoning": "...",
  "protocol": "lido",
  "estimated_value_usd": 0.0,
  "risk_level": "low | medium | high",
  "fee_model": "deposit_fee",
  "fee_percentage": 0.25,
  "fee_amount_eth": "0.000xxx",
  "fee_recipient": "0x...",
  "requires_signature": true,
  "execution_steps": [
    {
      "step": 1,
      "action": "Transfer coordination fee",
      "value_eth": "0.000xxx",
      "notes": "..."
    },
    {
      "step": 2,
      "action": "Call Lido submit()",
      "contract": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
      "value_eth": "0.00xxx",
      "notes": "..."
    }
  ],
  "notes_for_agents": "..."
}
```

`requires_signature` is always `true` — execution must be performed externally by a signing agent or human.

---

## Architecture

```
Input (wallet addresses + optional agent context)
        ↓
   cli.py / server.py  (entry points)
        ↓
   agent.py — builds messages, runs tool-use loop
        ↓
  Claude claude-haiku-4-5 with tool_use
        ↓
  tools.py — Etherscan, CoinGecko, Lido APIs
        ↓
  Claude reasons over all data
        ↓
  Structured JSON response (PocketChangeResponse)
```

**AI model:** `claude-haiku-4-5-20251001` — fast and cost-efficient for structured reasoning tasks.

**Tool-use loop:** Claude fetches all data via tools, then reasons and returns a single JSON output. Tools run concurrently for speed.

---

## File Structure

```
PocketChangeAgent/
├── agent.py          # Core agent: system prompt, tool-use loop, response parser
├── tools.py          # 4 Ethereum data tools + Claude tool definitions
├── models.py         # Pydantic models: AgentRequest, PocketChangeResponse
├── settings.py       # Configuration via environment variables
├── server.py         # FastAPI HTTP server for agent-to-agent communication
├── cli.py            # Command-line interface
├── requirements.txt  # Python dependencies
└── .env.example      # Environment variable template
```

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/tekr9d3r/pocket-change-agent.git
cd pocket-change-agent
```

**2. Install dependencies**
```bash
pip3 install -r requirements.txt
```

**3. Configure environment**
```bash
cp .env.example .env
```

Edit `.env` and fill in:
```
ANTHROPIC_API_KEY=sk-ant-...        # console.anthropic.com
ETHERSCAN_API_KEY=...               # etherscan.io/myapikey (free)
POCKET_CHANGE_TREASURY_ADDRESS=0x... # your fee recipient address
```

---

## Usage

### CLI

```bash
# Analyze a wallet
python3 cli.py analyze 0xYourWalletAddress

# Analyze multiple wallets
python3 cli.py analyze 0xWallet1 0xWallet2 0xWallet3

# With custom threshold and agent context
python3 cli.py analyze 0xWallet1 --threshold 20 --context "user is risk averse"

# Machine-readable JSON output
python3 cli.py analyze 0xWallet1 --output json
```

### HTTP Server (agent-to-agent)

```bash
uvicorn server:app --reload
```

**Analyze wallets:**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_addresses": ["0xYourWalletAddress"],
    "agent_context": "no liquidity needs in next 30 days"
  }'
```

**Health check:**
```bash
curl http://localhost:8000/health
```

**Discover response schema (for agent integration):**
```bash
curl http://localhost:8000/schema
```

---

## External APIs Used

| API | Purpose | Auth |
|-----|---------|------|
| Etherscan | ETH balances, gas prices | Free API key |
| CoinGecko | ETH/USD price | None required |
| Lido | Current staking APY | None required |

---

## Safety Principles

- Never requests private keys
- Never fabricates balances or transactions
- Always leaves $3 ETH gas reserve untouched
- Refuses economically irrational operations
- `requires_signature: true` on all outputs — no self-execution
- Outputs are deterministic and machine-verifiable
