from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    llm_api_key: str
    llm_api_endpoint: str
    app_name: str = "AI Form Filler Backend"
    cors_origins: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

@lru_cache()
def get_settings() -> Settings:
    return Settings() 