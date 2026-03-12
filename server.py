from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
