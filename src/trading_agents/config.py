from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    HIGH_VOLATILITY = "high_volatility"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


class RiskConfig(BaseSettings):
    max_position_pct: float = Field(default=0.05, description="Max % of portfolio per position")
    max_sector_pct: float = Field(default=0.25, description="Max % in one sector")
    max_daily_loss_pct: float = Field(default=0.02, description="Daily loss circuit breaker")
    max_leverage: float = Field(default=1.0, description="Max gross leverage")
    min_confidence: float = Field(default=0.55, description="Min agent confidence to trade")
    max_orders_per_day: int = Field(default=20)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRADING_", env_file=".env", extra="ignore")

    mode: TradingMode = TradingMode.PAPER
    symbols: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "AAPL"])
    risk: RiskConfig = Field(default_factory=RiskConfig)
    llm_provider: str = "mock"
    llm_model: str = "gpt-4o"
    debate_rounds: int = 1
    log_level: str = "INFO"


settings = Settings()
