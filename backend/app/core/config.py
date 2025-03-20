from pydantic_settings import BaseSettings, SettingsConfigDict

model_config = SettingsConfigDict(
    env_file=".env", env_ignore_empty=True, extra="ignore"
)


class PostgresSettings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_ASYNC_PREFIX: str

    @property
    def POSTGRES_URI(self) -> str:
        return f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


class SessionSettings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int


class Settings(PostgresSettings, SessionSettings):
    pass


settings = Settings()
