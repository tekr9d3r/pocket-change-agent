from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent import AgentError, run_agent_loop
from models import AgentRequest, PocketChangeResponse
from settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if required env vars are missing
    required = ["ANTHROPIC_API_KEY", "ETHERSCAN_API_KEY"]
    for var in required:
        if not getattr(settings, var, None):
            raise RuntimeError(f"Missing required environment variable: {var}")
    yield


app = FastAPI(
    title="PocketChange",
    description="Autonomous Ethereum yield coordination agent. Analyzes idle ETH balances and recommends Lido staking.",
    version="1.0.0",
    lifespan=lifespan,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=settings.PORT, reload=True)
