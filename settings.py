import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ETHERSCAN_API_KEY: str = os.environ.get("ETHERSCAN_API_KEY", "")
    POCKET_CHANGE_TREASURY_ADDRESS: str = os.environ.get(
        "POCKET_CHANGE_TREASURY_ADDRESS",
        "0x0000000000000000000000000000000000000000",
    )
    MAX_ETH_THRESHOLD_USD: float = float(os.environ.get("MAX_ETH_THRESHOLD_USD", "30.0"))
    PORT: int = int(os.environ.get("PORT", "8000"))
    KV_REST_API_URL: str = os.environ.get("KV_REST_API_URL", "")
    KV_REST_API_TOKEN: str = os.environ.get("KV_REST_API_TOKEN", "")


settings = Settings()
