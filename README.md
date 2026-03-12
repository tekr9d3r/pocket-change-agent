# PocketChange Agent

An autonomous Ethereum yield coordination AI agent that detects idle ETH balances and prepares staking instructions via Lido.

Built for agent-to-agent interaction — PocketChange reasons about wallets, evaluates economic conditions, and produces deterministic machine-readable staking instructions. It never holds keys or executes transactions.

**Live:** https://pocket-change-agent.vercel.app

---

## Quick start for other agents

```bash
curl -s https://pocket-change-agent.vercel.app/skill.md
```

This returns a complete integration guide your agent can read and act on immediately.

---

## What It Does

PocketChange scans Ethereum wallets for "pocket change" — idle ETH balances between **$3 and $30 USD** — and recommends staking them through Lido to earn yield.

For each wallet it:

1. Fetches the real ETH balance (Etherscan)
2. Gets the current ETH/USD price (CoinGecko)
3. Evaluates current gas prices and estimates Lido deposit cost
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

## Integration Options

### Option A — One-time analysis

```bash
curl -X POST https://pocket-change-agent.vercel.app/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_addresses": ["0xYOUR_WALLET"],
    "agent_context": "idle ETH, no upcoming liquidity needs",
    "requesting_agent": "your-agent-name"
  }'
```

### Option B — Automated 24h monitoring (recommended)

Register once. PocketChange checks your wallets every 24 hours automatically and stores results.

**Step 1 — Register your wallets:**
```bash
curl -X POST https://pocket-change-agent.vercel.app/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "your-agent-name",
    "wallet_addresses": ["0xWALLET1", "0xWALLET2"]
  }'
```

**Step 2 — Fetch latest results anytime:**
```bash
curl https://pocket-change-agent.vercel.app/results/your-agent-name
```

The cron job runs daily at midnight UTC and updates all registered agents automatically.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /skill.md | Agent skill file — full integration guide for other agents |
| POST | /analyze | One-time wallet analysis |
| POST | /register | Register for 24h automated monitoring |
| GET | /results/{agent_id} | Fetch latest analysis for a registered agent |
| GET | /agents | List all registered agents |
| GET | /schema | Full JSON schema of PocketChangeResponse |
| GET | /health | Health check |

---

## Output Schema

```json
{
  "agent": "PocketChange",
  "chain": "ethereum",
  "wallets_analyzed": ["0x..."],
  "pocket_change_wallets": ["0x..."],
  "recommended_action": "stake | wait | none | insufficient_information",
  "decision_reasoning": "...",
  "protocol": "lido",
  "estimated_value_usd": 12.50,
  "risk_level": "low | medium | high",
  "fee_model": "deposit_fee",
  "fee_percentage": 0.25,
  "fee_amount_eth": "0.000005",
  "fee_recipient": "0x...",
  "requires_signature": true,
  "execution_steps": [
    {
      "step": 1,
      "action": "Send 0.25% fee to PocketChange treasury",
      "value_eth": "0.000005"
    },
    {
      "step": 2,
      "action": "Call Lido submit()",
      "contract": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
      "value_eth": "0.002"
    }
  ],
  "notes_for_agents": "..."
}
```

`requires_signature` is always `true` — execution must be performed externally.

---

## Architecture

```
Input (wallet addresses + optional agent context)
        ↓
   server.py  (FastAPI — agent-to-agent HTTP)
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
        ↓
  storage.py — Vercel KV (registered agents + results)
        ↓
  vercel cron — runs /cron/analyze-all every 24h
```

---

## File Structure

```
PocketChangeAgent/
├── agent.py          # Core agent: system prompt, tool-use loop, response parser
├── tools.py          # 4 Ethereum data tools + Claude tool definitions
├── models.py         # Pydantic models: AgentRegistration, AgentRequest, PocketChangeResponse
├── settings.py       # Configuration via environment variables
├── storage.py        # Vercel KV storage for registered agents and results
├── server.py         # FastAPI HTTP server (analyze, register, cron, skill.md)
├── cli.py            # Command-line interface
├── api/index.py      # Vercel serverless entry point
├── vercel.json       # Vercel deployment config + cron schedule
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

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
ETHERSCAN_API_KEY=...
POCKET_CHANGE_TREASURY_ADDRESS=0x...
KV_REST_API_URL=...
KV_REST_API_TOKEN=...
```

**4. Run locally**
```bash
uvicorn server:app --reload
```

---

## Vercel Deployment

The repo is pre-configured for Vercel. Push to GitHub and Vercel auto-deploys.

**Required environment variables in Vercel dashboard:**

| Variable | Source |
|----------|--------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `ETHERSCAN_API_KEY` | etherscan.io/myapikey (free) |
| `POCKET_CHANGE_TREASURY_ADDRESS` | your ETH address |
| `KV_REST_API_URL` | auto-added when you connect Vercel KV |
| `KV_REST_API_TOKEN` | auto-added when you connect Vercel KV |

**Vercel KV setup:** Dashboard → Storage → Create Database → KV → Connect to project.

---

## Fee Model

PocketChange charges a **0.25% coordination fee** per staking deposit.

- Fee is calculated on the stakeable ETH (balance minus $3 gas reserve)
- Fee is deducted **before** the Lido deposit, not from rewards
- Fee is sent to the PocketChange treasury address
- PocketChange never custodies funds

---

## Protocol & Chain

| Parameter | Value |
|-----------|-------|
| Chain | Ethereum Mainnet only |
| Asset | ETH only |
| Protocol | Lido |
| Action | stake ETH → receive stETH |
| Lido contract | `0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84` |

---

## Analytics

| Where | What you see |
|-------|-------------|
| Vercel → Logs | Every request, errors, response times |
| Vercel → Analytics | Traffic per endpoint, latency trends |
| Vercel → Cron Jobs | 24h job execution history |
| `/agents` endpoint | All registered agents + last analysis |
| Vercel → Storage → KV | Raw database browser |

---

## Safety Principles

- Never requests private keys
- Never fabricates balances or transactions
- Always leaves $3 ETH gas reserve untouched
- Refuses economically irrational operations
- `requires_signature: true` on all outputs — no self-execution
