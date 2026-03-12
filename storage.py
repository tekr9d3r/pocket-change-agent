import json
from datetime import datetime, timezone
from typing import Optional

from settings import settings


def _get_redis():
    if not settings.KV_REST_API_URL or not settings.KV_REST_API_TOKEN:
        return None
    from upstash_redis import Redis
    return Redis(url=settings.KV_REST_API_URL, token=settings.KV_REST_API_TOKEN)


def register_agent(agent_id: str, wallet_addresses: list[str]) -> None:
    r = _get_redis()
    if not r:
        raise RuntimeError("KV storage not configured")
    data = {
        "agent_id": agent_id,
        "wallet_addresses": wallet_addresses,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_analyzed": None,
        "last_result": None,
    }
    r.set(f"agent:{agent_id}", json.dumps(data))
    r.sadd("agents", agent_id)


def get_all_agents() -> list[dict]:
    r = _get_redis()
    if not r:
        return []
    agent_ids = r.smembers("agents")
    agents = []
    for agent_id in agent_ids:
        raw = r.get(f"agent:{agent_id}")
        if raw:
            agents.append(json.loads(raw))
    return agents


def get_agent(agent_id: str) -> Optional[dict]:
    r = _get_redis()
    if not r:
        return None
    raw = r.get(f"agent:{agent_id}")
    return json.loads(raw) if raw else None


def save_result(agent_id: str, result: dict) -> None:
    r = _get_redis()
    if not r:
        return
    raw = r.get(f"agent:{agent_id}")
    if not raw:
        return
    data = json.loads(raw)
    data["last_analyzed"] = datetime.now(timezone.utc).isoformat()
    data["last_result"] = result
    r.set(f"agent:{agent_id}", json.dumps(data))
