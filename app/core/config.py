from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "options-api"
    DEBUG: bool = False
    DATABASE_URL: str
    API_KEY: str
    DATA_PROVIDER_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
