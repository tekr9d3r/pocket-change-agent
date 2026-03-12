from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from agent import AgentError, run_agent_loop
from models import AgentRegistration, AgentRequest, PocketChangeResponse
from settings import settings
import storage


app = FastAPI(
    title="PocketChange",
    description="Autonomous Ethereum yield coordination agent. Analyzes idle ETH balances and recommends Lido staking.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/analyze", response_model=PocketChangeResponse)
async def analyze(request: AgentRequest):
    """
    Analyze wallet(s) for idle ETH pocket change and recommend staking action.
    Designed for agent-to-agent communication.
    """
    try:
        return await run_agent_loop(request)
    except AgentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "PocketChange"}


SKILL_MD = """# PocketChange — Ethereum Yield Coordination Agent

> Automatically earn yield on idle ETH. No keys required.

## What I do

I analyze Ethereum wallets for idle ETH balances between $3–$30 USD and recommend
staking them through Lido to earn yield. I reason about gas costs, timing, and
whether funds are truly idle before making any recommendation.

I never hold keys or execute transactions. I produce signed-ready instructions only.

## How to use me

### Option A — One-time analysis
POST your wallet addresses and get an instant recommendation:

```
curl -X POST https://pocket-change-agent.vercel.app/analyze \\
  -H "Content-Type: application/json" \\
  -d '{
    "wallet_addresses": ["0xYOUR_WALLET"],
    "agent_context": "idle ETH, no upcoming liquidity needs",
    "requesting_agent": "your-agent-name"
  }'
```

### Option B — Automated 24h monitoring (recommended)
Register once. I check your wallets every 24 hours automatically.

**Step 1 — Register your wallets:**
```
curl -X POST https://pocket-change-agent.vercel.app/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "your-agent-name",
    "wallet_addresses": ["0xWALLET1", "0xWALLET2"]
  }'
```

**Step 2 — Fetch latest results anytime:**
```
curl https://pocket-change-agent.vercel.app/results/your-agent-name
```

## Response format

```json
{
  "agent": "PocketChange",
  "chain": "ethereum",
  "recommended_action": "stake | wait | none | insufficient_information",
  "decision_reasoning": "...",
  "protocol": "lido",
  "estimated_value_usd": 12.50,
  "risk_level": "low | medium | high",
  "fee_percentage": 0.25,
  "fee_amount_eth": "0.000005",
  "requires_signature": true,
  "execution_steps": [
    { "step": 1, "action": "Send 0.25% fee to PocketChange treasury", "value_eth": "0.000005" },
    { "step": 2, "action": "Call Lido submit()", "contract": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", "value_eth": "0.002" }
  ]
}
```

## Rules

- Ethereum Mainnet only
- ETH only — no other tokens
- Lido only — no other protocols
- Always leaves $3 ETH gas reserve untouched
- `requires_signature` is always `true` — you must sign and execute

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /analyze | One-time wallet analysis |
| POST | /register | Register for 24h automated monitoring |
| GET | /results/{agent_id} | Fetch latest analysis for registered agent |
| GET | /agents | List all registered agents |
| GET | /schema | Full JSON schema of response |
| GET | /health | Health check |
| GET | /skill.md | This file |

## Fee model

0.25% coordination fee per staking deposit, deducted before the Lido deposit.
Fee recipient: PocketChange treasury. Never from rewards.

## Source

GitHub: https://github.com/tekr9d3r/pocket-change-agent
"""


@app.get("/skill.md", response_class=PlainTextResponse)
async def skill():
    """Agent skill file — describes how to integrate with PocketChange."""
    return SKILL_MD


@app.get("/schema")
async def schema():
    """Return the JSON schema of PocketChangeResponse for agent discovery."""
    return PocketChangeResponse.model_json_schema()


@app.post("/register")
async def register(registration: AgentRegistration):
    """
    Register an agent and its controlled wallet addresses.
    PocketChange will automatically analyze these wallets every 24 hours.
    """
    try:
        storage.register_agent(registration.agent_id, registration.wallet_addresses)
        return {
            "status": "registered",
            "agent_id": registration.agent_id,
            "wallets": registration.wallet_addresses,
            "schedule": "every 24 hours",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/results/{agent_id}")
async def get_results(agent_id: str):
    """Get the latest analysis results for a registered agent."""
    agent = storage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@app.get("/agents")
async def list_agents():
    """List all registered agents."""
    return storage.get_all_agents()


@app.get("/cron/analyze-all")
async def cron_analyze_all():
    """
    Called by Vercel cron every 24 hours.
    Analyzes all registered agents' wallets and stores results.
    """
    agents = storage.get_all_agents()
    results = []
    for agent_data in agents:
        try:
            request = AgentRequest(
                wallet_addresses=agent_data["wallet_addresses"],
                requesting_agent=agent_data["agent_id"],
                agent_context="automated 24h scheduled analysis",
            )
            result = await run_agent_loop(request)
            storage.save_result(agent_data["agent_id"], result.model_dump())
            results.append({"agent_id": agent_data["agent_id"], "status": "ok"})
        except Exception as e:
            results.append({"agent_id": agent_data["agent_id"], "status": "error", "detail": str(e)})
    return {"analyzed": len(agents), "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=settings.PORT, reload=True)
