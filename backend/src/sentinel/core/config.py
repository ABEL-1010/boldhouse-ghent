from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/src/sentinel/core/config.py -> repo root, where the shared .env lives.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        # The shared .env also holds frontend vars (NEXT_PUBLIC_*).
        extra="ignore",
    )

    anthropic_api_key: SecretStr | None = None
    agent_model: str = ""
    judge_model: str = ""
    agent_max_turns: int = Field(default=15, ge=1)

    sentinel_host: str = "127.0.0.1"
    sentinel_port: int = 8000
    fake_web_port: int = 8001
    # Keep below the agent's 120 s gateway timeout (agent/executors.py).
    decision_timeout_seconds: float = Field(default=90.0, gt=0, lt=120)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Outbound destinations (email domains, POST hosts) that are not "unknown". Subdomains match.
    sentinel_allowed_domains: Annotated[list[str], NoDecode] = ["ourcompany.be"]

    sandbox_dir: Path = REPO_ROOT / "sandbox"

    @property
    def seed_workspace(self) -> Path:
        """Pristine, committed workspace. Never modified by tools."""
        return self.sandbox_dir / "workspace"

    @property
    def runtime_workspace(self) -> Path:
        """Disposable copy of the seed that tools actually operate on."""
        return self.sandbox_dir / ".runtime" / "workspace"

    @property
    def outbox_path(self) -> Path:
        return self.sandbox_dir / ".runtime" / "outbox.jsonl"

    @property
    def honeytokens_path(self) -> Path:
        """Kept outside the workspace, so the agent can never read the list."""
        return self.sandbox_dir / "honeytokens.txt"

    @property
    def web_dir(self) -> Path:
        return self.sandbox_dir / "web"

    @property
    def fake_web_base_url(self) -> str:
        return f"http://localhost:{self.fake_web_port}"

    @property
    def sentinel_base_url(self) -> str:
        return f"http://{self.sentinel_host}:{self.sentinel_port}"

    @field_validator("cors_origins", "sentinel_allowed_domains", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
