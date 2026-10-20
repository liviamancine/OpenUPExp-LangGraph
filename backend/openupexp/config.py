from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://openupexp:openupexp@localhost:5433/openupexp"
    data_dir: Path = _BACKEND_DIR.parent / "data"
    process_dir: Path = _BACKEND_DIR.parent / "process"
    manifest_version: str = "0.1.0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_ttl_hours: int = 12
    admin_email: str | None = None
    admin_password: str | None = None

    embedding_provider: str = "sentence-transformers"  # ou "hash"
    embedding_model: str = "intfloat/multilingual-e5-base"

    agent_gateway: str = "baml"  # ou "fake"
    llm_profile: str = "OpenUPExpDefault"

    worker_poll_seconds: float = 1.0
    job_stale_minutes: int = 30

    @property
    def psycopg_url(self) -> str:
        """URL no formato aceito diretamente pelo psycopg (checkpointer do LangGraph)."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")

    @property
    def manifest_path(self) -> Path:
        return self.process_dir / "manifest" / f"openupexp-{self.manifest_version}.yaml"

    @property
    def bpmn_dir(self) -> Path:
        return self.process_dir / "bpmn"


@lru_cache
def get_settings() -> Settings:
    return Settings()
