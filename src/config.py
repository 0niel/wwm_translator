from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Self

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


if TYPE_CHECKING:
    from typing import Any

load_dotenv()


class PathsConfig(BaseModel):
    """File paths configuration with automatic Path conversion."""

    model_config = {"arbitrary_types_allowed": True}

    game_locale_dir: Path
    work_dir: Path = Path("./data")
    source_dir: Path = Path("./data/source")
    translated_dir: Path = Path("./data/translated")
    progress_dir: Path = Path("./data/progress")
    rules_dir: Path = Path("./rules")

    @field_validator("*", mode="before")
    @classmethod
    def _convert_to_path(cls, v: Any) -> Path:
        return Path(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def _ensure_directories(self) -> Self:
        """Ensure all directories exist."""
        for field_name in self.model_fields:
            path = getattr(self, field_name)
            if isinstance(path, Path) and not path.suffix:  # Directory, not file
                path.mkdir(parents=True, exist_ok=True)
        return self


class LanguagesConfig(BaseModel):
    """Languages configuration."""

    original: str = "zh_cn"
    source: str = "en"
    target: str = "ru"
    patch_lang: str = "de"  # Language to patch (replace with translations)
    context_languages: list[str] = Field(default_factory=list)

    @cached_property
    def display_names(self) -> dict[str, str]:
        """Human-readable language names."""
        names = {
            "zh_cn": "Chinese (Simplified)",
            "zh_tw": "Chinese (Traditional)",
            "en": "English",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
        }
        return names


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "openrouter"
    model: str = "x-ai/grok-4.1-fast:free"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout: int = Field(default=120, gt=0)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: int = Field(default=5, gt=0)

    @property
    def is_free_tier(self) -> bool:
        """Check if using free tier model."""
        return ":free" in self.model.lower()


class BatchConfig(BaseModel):
    """Batch processing configuration."""

    size: int = Field(default=15, gt=0, le=100)
    context_before: int = Field(default=3, ge=0)
    context_after: int = Field(default=3, ge=0)
    max_tokens_per_batch: int = Field(default=6000, gt=0)
    concurrent_requests: int = Field(default=1, ge=1)
    delay_between_batches: float = Field(default=2.0, ge=0.0)


class ProgressConfig(BaseModel):
    """Progress tracking configuration."""

    save_every_n_batches: int = Field(default=5, gt=0)
    create_backups: bool = True
    max_backups: int = Field(default=3, ge=0)


class FilteringConfig(BaseModel):
    """Text filtering configuration."""

    skip_empty: bool = True
    skip_tags_only: bool = True
    min_length: int = Field(default=2, ge=0)
    skip_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^\{.*\}$",
            r"^\d+$",
            r"^[\s\p{P}]+$",
        ]
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "./logs/translator.log"
    console: bool = True
    time_format: str = "%Y-%m-%d %H:%M:%S"


class AppConfig(BaseModel):
    """Main application configuration."""

    paths: PathsConfig
    languages: LanguagesConfig = Field(default_factory=LanguagesConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    batch: BatchConfig = Field(default_factory=BatchConfig)
    progress: ProgressConfig = Field(default_factory=ProgressConfig)
    filtering: FilteringConfig = Field(default_factory=FilteringConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def get_source_csv(self) -> Path:
        """Get path to source language CSV."""
        return self.paths.source_dir / "csv" / f"{self.languages.source}.csv"

    def get_original_csv(self) -> Path:
        """Get path to original language CSV."""
        return self.paths.source_dir / "csv" / f"{self.languages.original}.csv"

    def get_output_csv(self) -> Path:
        """Get path to translated CSV."""
        return self.paths.translated_dir / f"{self.languages.target}.csv"


class EnvConfig(BaseSettings):
    """Environment variables for API keys, model, and pricing."""

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_base: str | None = Field(default=None, alias="OPENAI_API_BASE")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    token_price_input: float = Field(default=0.0, alias="TOKEN_PRICE_INPUT")
    token_price_output: float = Field(default=0.0, alias="TOKEN_PRICE_OUTPUT")

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_api_key(self, provider: str) -> str | None:
        """Get API key for provider."""
        match provider.lower():
            case "openrouter":
                return self.openrouter_api_key
            case "openai":
                return self.openai_api_key
            case "anthropic":
                return self.anthropic_api_key
            case "google":
                return self.google_api_key
            case _:
                return None


# Global config singleton
@dataclass(slots=True)
class ConfigManager:
    """Configuration manager singleton."""

    _app_config: AppConfig | None = None
    _env_config: EnvConfig | None = None

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> tuple[AppConfig, EnvConfig]:
        """Load configuration from file."""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with config_file.open(encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        cls._app_config = AppConfig(**config_data)
        cls._env_config = EnvConfig()

        if cls._env_config.llm_model:
            cls._app_config.llm.model = cls._env_config.llm_model

        Path(cls._app_config.logging.file).parent.mkdir(parents=True, exist_ok=True)

        return cls._app_config, cls._env_config

    @classmethod
    def get_app_config(cls) -> AppConfig:
        """Get application config."""
        if cls._app_config is None:
            cls.load()
        return cls._app_config  # type: ignore

    @classmethod
    def get_env_config(cls) -> EnvConfig:
        """Get environment config."""
        if cls._env_config is None:
            cls.load()
        return cls._env_config  # type: ignore


def init_config(config_path: str = "config.yaml") -> tuple[AppConfig, EnvConfig]:
    """Initialize configuration."""
    return ConfigManager.load(config_path)


def get_config() -> AppConfig:
    """Get application config."""
    return ConfigManager.get_app_config()


def get_env_config() -> EnvConfig:
    """Get environment config."""
    return ConfigManager.get_env_config()
