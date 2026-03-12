import asyncio
import json
import math
import os

import httpx

from settings import settings


def _etherscan_key() -> str:
    return settings.ETHERSCAN_API_KEY or os.environ.get("ETHERSCAN_API_KEY", "")

# Lido stETH deposit uses ~120k gas (conservative estimate)
LIDO_DEPOSIT_GAS_UNITS = 120_000


async def get_eth_balance(wallet_address: str) -> dict:
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": "1",
        "module": "account",
        "action": "balance",
        "address": wallet_address,
        "tag": "latest",
        "apikey": _etherscan_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                return {"wallet": wallet_address, "error": data.get("message", "Etherscan error")}
            balance_wei = int(data["result"])
            balance_eth = balance_wei / 1e18
            return {
                "wallet": wallet_address,
                "balance_wei": str(balance_wei),
                "balance_eth": balance_eth,
            }
    except httpx.TimeoutException:
        return {"wallet": wallet_address, "error": "timeout"}
    except Exception as e:
        return {"wallet": wallet_address, "error": str(e)}


async def get_eth_price_usd() -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "ethereum", "vs_currencies": "usd"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            price = data["ethereum"]["usd"]
            return {"price_usd": price, "source": "coingecko"}
    except httpx.TimeoutException:
        return {"error": "timeout", "source": "coingecko"}
    except Exception as e:
        return {"error": str(e), "source": "coingecko"}


async def get_gas_price() -> dict:
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": "1",
        "module": "gastracker",
        "action": "gasoracle",
        "apikey": _etherscan_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                return {"error": data.get("message", "Etherscan gas oracle error")}
            result = data["result"]
            propose_gwei = float(result["ProposeGasPrice"])
            safe_gwei = float(result["SafeGasPrice"])
            fast_gwei = float(result["FastGasPrice"])
            base_fee_gwei = float(result.get("suggestBaseFee", propose_gwei))
            # Estimate cost of Lido deposit at proposed gas price
            deposit_cost_eth = (LIDO_DEPOSIT_GAS_UNITS * propose_gwei) / 1e9
            return {
                "safe_gas_gwei": safe_gwei,
                "propose_gas_gwei": propose_gwei,
                "fast_gas_gwei": fast_gwei,
                "base_fee_gwei": base_fee_gwei,
                "estimated_lido_deposit_cost_eth": deposit_cost_eth,
            }
    except httpx.TimeoutException:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


async def get_lido_apy() -> dict:
    url = "https://eth-api.lido.fi/v1/protocol/steth/apr/sma"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            apr = float(data["data"]["smaApr"])
            # Convert APR to APY: (1 + apr/365)^365 - 1
            apy = (1 + apr / 100 / 365) ** 365 - 1
            return {
                "apr_percent": apr,
                "apy_percent": round(apy * 100, 4),
                "sma_period_days": data["data"].get("timeRange", "unknown"),
                "source": "lido",
            }
    except httpx.TimeoutException:
        return {"apy_percent": 3.5, "source": "lido_fallback", "fallback": True, "error": "timeout"}
    except Exception as e:
        return {"apy_percent": 3.5, "source": "lido_fallback", "fallback": True, "error": str(e)}


# Semaphore to respect Etherscan free-tier rate limit (5 req/sec)
_etherscan_semaphore = asyncio.Semaphore(4)

_TOOL_FUNCTIONS = {
    "get_eth_balance": get_eth_balance,
    "get_eth_price_usd": get_eth_price_usd,
    "get_gas_price": get_gas_price,
    "get_lido_apy": get_lido_apy,
}


_ETHERSCAN_TOOLS = {"get_eth_balance", "get_gas_price"}


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    fn = _TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    if tool_name in _ETHERSCAN_TOOLS:
        async with _etherscan_semaphore:
            result = await fn(**tool_input)
    else:
        result = await fn(**tool_input)
    return json.dumps(result)


TOOL_DEFINITIONS = [
    {
        "name": "get_eth_balance",
        "description": (
            "Fetch the current ETH balance of a single wallet address from Etherscan. "
            "Call once per wallet address provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "wallet_address": {
                    "type": "string",
                    "description": "Ethereum wallet address starting with 0x (42 characters total)",
                }
            },
            "required": ["wallet_address"],
        },
    },
    {
        "name": "get_eth_price_usd",
        "description": (
            "Fetch the current ETH/USD price from CoinGecko. "
            "Call once to get the price needed for USD value calculations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_gas_price",
        "description": (
            "Fetch current Ethereum gas prices and the estimated ETH cost of a Lido stETH deposit "
            "transaction (estimated_lido_deposit_cost_eth). Use this to evaluate whether gas costs "
            "make staking economically viable relative to the balance size."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_lido_apy",
        "description": (
            "Fetch the current Lido stETH staking APY. "
            "Use this to calculate projected annual yield and inform the stake vs. wait decision."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
