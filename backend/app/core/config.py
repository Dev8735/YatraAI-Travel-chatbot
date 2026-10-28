"""Application settings loaded from environment variables (and an optional .env file).

Every external integration is optional. When a credential is missing the related
feature falls back to a clearly labelled demo mode instead of failing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    seed_demo_data: bool = True

    # --- Database ----------------------------------------------------------
    # Postgres in Docker/production; SQLite is the zero-setup local default.
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{(DATA_DIR / 'yatra.db').as_posix()}"
    )

    # --- Vector store ------------------------------------------------------
    # If QDRANT_URL is set a Qdrant server is used; otherwise embedded local mode.
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str = str(DATA_DIR / "qdrant")
    qdrant_collection: str = "yatra_chunks"

    # --- Embeddings --------------------------------------------------------
    # "sentence_transformers" uses a real multilingual model (requires
    # requirements-ml.txt). "hashing" is a deterministic lexical fallback.
    embedding_backend: Literal["auto", "sentence_transformers", "hashing"] = "auto"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    hashing_dim: int = 512

    # --- LLM -------------------------------------------------------------
    llm_provider: Literal["auto", "anthropic", "openai", "ollama", "demo"] = "auto"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str | None = None
    ollama_model: str = "llama3"
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 2048

    # --- Retrieval -------------------------------------------------------
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.2
    chunk_size: int = 900
    chunk_overlap: int = 150
    history_turns: int = 8

    # --- Crawling --------------------------------------------------------
    crawler_user_agent: str = "YatraAI-Bot/0.1 (+https://github.com/Dev8735/YatraAI-Travel-chatbot)"
    crawl_max_pages: int = 25
    crawl_max_depth: int = 2
    crawl_timeout_seconds: float = 15.0
    crawl_max_bytes: int = 2_000_000
    crawl_max_redirects: int = 5
    crawl_delay_seconds: float = 0.5
    # Only for local testing against your own machine. Never enable in production.
    crawl_allow_private_networks: bool = False

    # --- Travel providers --------------------------------------------------
    google_maps_api_key: str | None = None
    google_places_language: str = "en"
    places_provider: Literal["auto", "google", "demo"] = "auto"
    routes_provider: Literal["auto", "google", "none"] = "auto"
    transport_provider: Literal["none"] = "none"
    # Browser key for the map embed. Must be restricted by HTTP referrer in Google Cloud.
    next_public_google_maps_embed_key: str | None = None

    # --- Abuse protection --------------------------------------------------
    rate_limit_chat_per_minute: int = 30
    rate_limit_ingest_per_hour: int = 10
    rate_limit_providers_per_minute: int = 60
    max_message_chars: int = 2000

    @field_validator(
        "anthropic_api_key",
        "openai_api_key",
        "google_maps_api_key",
        "qdrant_url",
        "qdrant_api_key",
        "ollama_base_url",
        "openai_base_url",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and (not v.strip() or v.strip().startswith("your-")):
            return None
        return v

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY")
        if self.llm_provider == "ollama" and not self.ollama_base_url:
            raise ValueError("LLM_PROVIDER=ollama requires OLLAMA_BASE_URL (e.g. http://localhost:11434)")
        if self.places_provider == "google" and not self.google_maps_api_key:
            raise ValueError("PLACES_PROVIDER=google requires GOOGLE_MAPS_API_KEY")
        if self.routes_provider == "google" and not self.google_maps_api_key:
            raise ValueError("ROUTES_PROVIDER=google requires GOOGLE_MAPS_API_KEY")
        if self.app_env == "production" and self.crawl_allow_private_networks:
            raise ValueError("CRAWL_ALLOW_PRIVATE_NETWORKS must be false in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
