from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = ""
    openrouter_app_title: str = "AI Research Agent"
    tavily_api_key: str = ""
    searchapi_api_key: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/research_agent"


@lru_cache
def get_settings() -> Settings:
    return Settings()
