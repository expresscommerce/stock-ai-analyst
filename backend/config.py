"""Application configuration."""

import os
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()


class Config:
    """Base configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql://stockai:stockai_pass@localhost:5432/stockai"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Celery
    CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BEAT_SCHEDULE = {
        "fetch-prices": {
            "task": "app.tasks.fetch_prices.run",
            "schedule": crontab(minute="*/5"),
        },
        "fetch-news": {
            "task": "app.tasks.fetch_news.run",
            "schedule": crontab(minute=0),
        },
        "daily-report": {
            "task": "app.tasks.daily_report.run",
            "schedule": crontab(hour=9, minute=0),
        },
    }

    # DeepInfra
    DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY", "")
    DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
    DEEPINFRA_CHAT_MODEL = os.getenv("DEEPINFRA_CHAT_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    DEEPINFRA_EMBEDDING_MODEL = "BAAI/bge-m3"

    # NewsAPI
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

    # ExchangeRate-API
    EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")

    # Default tracked tickers
    DEFAULT_TICKERS = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "JPM", "JNJ",
        "QQQ", "SPY", "VTI",
        "BTC-USD", "ETH-USD",
        "GC=F", "CL=F", "SI=F",
    ]

    DEFAULT_INDICES = ["^GSPC", "^IXIC", "^FTSE", "^GDAXI", "^KSE"]

    SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "PKR", "AED", "SAR", "CAD", "AUD"]


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
