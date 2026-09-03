"""Runtime configuration, sourced from environment variables (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="PORTFOLIO_", extra="ignore"
    )

    # Where the DuckDB warehouse file lives. dbt reads the same file.
    duckdb_path: Path = REPO_ROOT / "data" / "warehouse.duckdb"

    # Root of the dbt project, used when the API triggers a `dbt build`.
    dbt_project_dir: Path = REPO_ROOT / "dbt" / "portfolio"

    # Provider preference order. "auto" walks the chain until one succeeds.
    provider: str = "auto"

    # Origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Price history cached on disk for this many minutes before refetching.
    cache_ttl_minutes: int = 60

    # Risk-free rate used for Sharpe ratios, as an annualized decimal.
    risk_free_rate: float = 0.042

    # Trading days per year, used to annualize daily statistics.
    trading_days: int = 252

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
