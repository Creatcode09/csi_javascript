import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    lan_host: str = "0.0.0.0"
    lan_port: int = 8000
    admin_key: str = "techfest-admin-secret-2026"
    
    # Times in seconds (15 minutes by default)
    part_a_duration: int = 900
    part_b_duration: int = 900
    buffer_duration: int = 10
    
    # SQLite DB path
    database_path: str = "exchange.db"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
