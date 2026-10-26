import os

from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # Binance API
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # News/Sentiment API
    newsapi_key: str = ""
    cryptopanic_key: str = ""

    # Database
    database_url: str = f"sqlite:///{os.path.join(BASE_DIR, 'trading_bot.db')}"

    # App
    app_name: str = "Trading Bot"
    debug: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
