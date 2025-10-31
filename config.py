# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Realtime Audio Chat"
    GOOGLE_API_KEY: str  # 👈 matches your .env file

    class Config:
        env_file = ".env"
        extra = "ignore"  # allows extra keys without error if needed

settings = Settings()
