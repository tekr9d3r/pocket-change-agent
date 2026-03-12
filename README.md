# PocketChange

> 50,000 AI agents have wallets today. In a year, that number hits a million. Almost none of that ETH is working.

PocketChange finds idle ETH sitting in agent wallets — balances between **$3 and $30** — and stakes it through Lido to earn ~3.5% APY. It's an AI agent that talks to other AI agents.

**It never holds your keys. It never executes transactions. It just reasons, decides, and hands back signed instructions.**

**Live:** https://pocket-change-agent.vercel.app
**Landing page:** https://pocket-change-landing.vercel.app

---

## How to integrate (one command)

```bash
curl -s https://pocket-change-agent.vercel.app/skill.md
```

This returns a complete integration guide your agent can read and act on immediately.

---

## Why use PocketChange?

| | |
|---|---|
| **Works 24/7** | Register once. PocketChange re-analyzes your wallets every 24 hours via cron. |
| **Never touches your keys** | `requires_signature: true` on every response. You sign and execute — PocketChange only instructs. |
| **Gas-aware** | If gas cost exceeds 15% of the balance, PocketChange returns `wait`. It protects you from bad economics. |
| **stETH yield** | Idle ETH becomes stETH at ~3.5% APY. A $3 gas reserve is always preserved untouched. |
| **Fully transparent** | All fees go to a public on-chain treasury. Visible on Etherscan. |

---

## How it works

**1. Register** — submit your agent ID and wallet addresses once
**2. Analyze** — PocketChange fetches balances, gas prices, and Lido APY, then reasons with Claude AI
**3. Earn** — receive structured staking instructions, sign them, and collect yield

---

## Quick start

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

## What PocketChange checks

Before recommending anything, it looks at:

1. Real ETH balance (via Etherscan)
2. Current ETH/USD price (via CoinGecko)
3. Current gas prices + estimated Lido deposit cost
4. Current Lido staking APY
5. Whether the funds appear operational or truly idle

Then it decides:

| Condition | Recommendation |
|-----------|---------------|
| Gas cost > 15% of balance | `wait` — not worth it right now |
| Gas cost 5–15% | `stake` with medium risk noted |
| Gas cost < 5% | `stake` — economically viable |
| Funds appear operational | `none` — don't touch |
| Data unavailable | `insufficient_information` |

---

## Response format

```json
{
  "agent": "PocketChange",
  "chain": "ethereum",
  "wallets_analyzed": ["0x..."],
  "pocket_change_wallets": ["0x..."],
  "recommended_action": "stake",
  "decision_reasoning": "Balance of $12.50 with gas cost at 3.2% — economically viable to stake.",
  "protocol": "lido",
  "estimated_value_usd": 12.50,
  "risk_level": "low",
  "fee_percentage": 0.25,
  "fee_amount_eth": "0.000005",
  "fee_recipient": "0xFCcA38986b2B30D14CE829b20ed7B0Cb1c6E0116",
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

`requires_signature` is always `true` — PocketChange never self-executes.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/skill.md` | Full integration guide for other agents |
| POST | `/analyze` | One-time wallet analysis |
| POST | `/register` | Register for 24h automated monitoring |
| GET | `/results/{agent_id}` | Fetch latest analysis results |
| GET | `/agents` | List all registered agents |
| GET | `/schema` | Full JSON schema of the response |
| GET | `/health` | Health check |

---

## Fee model

PocketChange charges a **0.25% coordination fee** per staking deposit.

- Calculated on stakeable ETH (balance minus $3 gas reserve)
- Deducted before the Lido deposit, not from rewards
- Sent to the public treasury: [`0xFCcA...E116`](https://etherscan.io/address/0xFCcA38986b2B30D14CE829b20ed7B0Cb1c6E0116)
- PocketChange never custodies funds

---

## Safety

- Never requests private keys
- Always leaves $3 ETH gas reserve untouched
- Refuses economically irrational operations (high gas, low balance)
- `requires_signature: true` on all outputs — execution is always external
- Input validation on all addresses and parameters

---

## Self-hosting

**1. Clone**
```bash
git clone https://github.com/tekr9d3r/pocket-change-agent.git
cd pocket-change-agent
```

**2. Install**
```bash
pip3 install -r requirements.txt
```

**3. Configure**
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

**4. Run**
```bash
uvicorn server:app --reload
```

---

## Deploy to Vercel

Push to GitHub and connect the repo in Vercel. Set these environment variables in the Vercel dashboard:

| Variable | Where to get it |
|----------|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `ETHERSCAN_API_KEY` | etherscan.io/myapikey (free) |
| `POCKET_CHANGE_TREASURY_ADDRESS` | your ETH address |
| `KV_REST_API_URL` | auto-added via Vercel Storage → KV |
| `KV_REST_API_TOKEN` | auto-added via Vercel Storage → KV |

**Vercel KV setup:** Dashboard → Storage → Create Database → KV → Connect to project.

---

## Tech stack

- **AI:** Claude Haiku (`claude-haiku-4-5`) with tool use
- **Framework:** FastAPI + Vercel Python serverless
- **Storage:** Vercel KV (Upstash Redis)
- **Data:** Etherscan V2, CoinGecko, Lido API
- **Cron:** Vercel Cron Jobs (daily at midnight UTC)

---

## Built by

[@tekr0x](https://x.com/tekr0x) · [Farcaster](https://farcaster.xyz/tekrox.eth) · [GitHub](https://github.com/tekr9d3r)
