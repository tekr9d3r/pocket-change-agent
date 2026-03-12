from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    ETHERSCAN_API_KEY: str = ""
    POCKET_CHANGE_TREASURY_ADDRESS: str = "0x0000000000000000000000000000000000000000"
    MAX_ETH_THRESHOLD_USD: float = 30.0
    PORT: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
