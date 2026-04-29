from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Keroyok.AI Backend"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    context_bank_dir: Path = Path("data/context_bank")
    use_microsoft_agent_framework: bool = True

    azure_foundry_endpoint: str | None = None
    azure_foundry_api_key: SecretStr | None = None
    azure_foundry_chat_deployment: str | None = None
    azure_foundry_embedding_deployment: str | None = None
    azure_foundry_api_version: str | None = None
    azure_use_default_credential: bool = False

    cosmos_endpoint: str | None = None
    cosmos_key: SecretStr | None = None
    cosmos_database: str | None = None
    cosmos_context_container: str = "context-bank"
    cosmos_pm_log_container: str = "pm-agent-logs"

    azure_ai_search_endpoint: str | None = None
    azure_ai_search_api_key: SecretStr | None = None
    azure_ai_search_index_name: str = "keroyok-context-bank"
    azure_ai_search_vector_dimensions: int = Field(default=1536, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def azure_foundry_api_key_value(self) -> str | None:
        if self.azure_foundry_api_key is None:
            return None
        return self.azure_foundry_api_key.get_secret_value()

    @property
    def azure_ai_search_api_key_value(self) -> str | None:
        if self.azure_ai_search_api_key is None:
            return None
        return self.azure_ai_search_api_key.get_secret_value()

    @property
    def cosmos_key_value(self) -> str | None:
        if self.cosmos_key is None:
            return None
        return self.cosmos_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
