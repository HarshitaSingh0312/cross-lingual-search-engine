from functools import lru_cache
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    embedding_model_name: str = "sentence-transformers/LaBSE"
    embedding_dim: int = 768

    # Existing ML core lives one level up from backend/; ingestion reads its cached data.
    ml_core_dir: str = "../cross_lingual_retrieval"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def async_database_url(self) -> str:
        """asyncpg driver, used by the running app. asyncpg doesn't understand
        libpq params like sslmode, so it's dropped here and passed as connect_args instead."""
        parsed = urlparse(self.database_url)
        query = dict(parse_qsl(parsed.query))
        query.pop("sslmode", None)
        return urlunparse(parsed._replace(scheme="postgresql+asyncpg", query=urlencode(query)))

    @property
    def sync_database_url(self) -> str:
        """psycopg2 driver, used only by Alembic migrations (which run synchronously)."""
        parsed = urlparse(self.database_url)
        return urlunparse(parsed._replace(scheme="postgresql+psycopg2"))

    @property
    def db_connect_args(self) -> dict:
        """asyncpg wants ssl passed as a connect arg, not a URL query param. Only require
        it when the source DATABASE_URL asked for it (Neon does; the local Docker Postgres
        container doesn't have SSL configured at all)."""
        parsed = urlparse(self.database_url)
        query = dict(parse_qsl(parsed.query))
        return {"ssl": "require"} if query.get("sslmode") == "require" else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
