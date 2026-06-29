"""Central configuration.

Settings are read from environment variables (and an optional ``.env`` file)
using ``pydantic-settings``. Everything has a sensible default so the system
runs end-to-end with zero configuration in offline mode.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OFFLINE = "offline"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DataSource(str, Enum):
    SYNTHETIC = "synthetic"
    YFINANCE = "yfinance"


class Settings(BaseSettings):
    """Runtime settings for the whole system.

    All fields are prefixed with ``STA_`` in the environment, e.g.
    ``STA_LLM_PROVIDER=openai``.
    """

    model_config = SettingsConfigDict(
        env_prefix="STA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---------------------------------------------------------------
    llm_provider: LLMProvider = LLMProvider.OFFLINE
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, gt=0)

    # Credentials are read from the conventional (un-prefixed) env vars too.
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    # --- Data --------------------------------------------------------------
    data_source: DataSource = DataSource.SYNTHETIC

    # --- Memory / runtime --------------------------------------------------
    memory_path: str = "runs/memory.json"
    verbose: bool = True

    # Reproducibility for the synthetic data generator and any sampling.
    random_seed: int = 42

    # --- Performance -------------------------------------------------------
    # Number of analyst agents to evaluate concurrently. ``1`` keeps the
    # original sequential, fully-ordered behaviour; higher values overlap the
    # (I/O-bound) live-LLM calls and are still deterministic thanks to the
    # graph engine's stable merge order.
    max_workers: int = Field(default=4, ge=1, le=16)

    # --- Risk policy -------------------------------------------------------
    # Target portfolio volatility used for vol-targeted position sizing.
    target_volatility: float = Field(default=0.20, gt=0.0, le=1.0)
    # Hard cap on any single position as a fraction of equity.
    max_position: float = Field(default=0.30, gt=0.0, le=1.0)
    # Fraction of the full-Kelly bet to use (0 disables Kelly blending).
    kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0)


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()
