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

    All fields are prefixed with ``TA_`` in the environment, e.g.
    ``TA_LLM_PROVIDER=openai``.
    """

    model_config = SettingsConfigDict(
        env_prefix="TA_",
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()
