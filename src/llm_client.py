from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import EnvConfig, LLMConfig, get_config, get_env_config
from .models import ErrorMarkers


logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base LLM client error."""
class RateLimitError(LLMClientError):
    """Rate limit exceeded - should retry with backoff."""
class QuotaExceededError(LLMClientError):
    """Quota exceeded - should not retry."""
class ConfigurationError(LLMClientError):
    """Configuration error - should not retry."""
class TransientError(LLMClientError):
    """Transient error - should retry."""
class IncompleteResponseError(LLMClientError):
    """LLM returned fewer items than expected - should retry."""
class ErrorType(Enum):
    """Error classification for retry decisions."""

    RATE_LIMIT = auto()
    QUOTA = auto()
    TRANSIENT = auto()
    PERMANENT = auto()


@dataclass(slots=True)
class RateLimiter:
    """Token bucket rate limiter for API calls."""

    requests_per_minute: int = 60
    _tokens: float = field(default=60.0, repr=False)
    _last_update: float = field(default_factory=time.time, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def acquire(self) -> None:
        """Wait until a request token is available."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(
                self.requests_per_minute, self._tokens + elapsed * (self.requests_per_minute / 60.0)
            )
            self._last_update = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / (self.requests_per_minute / 60.0)
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _failures: int = field(default=0, repr=False)
    _last_failure: float = field(default=0.0, repr=False)
    _state: str = field(default="closed", repr=False)  # closed, open, half-open

    def record_success(self) -> None:
        """Record successful call."""
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record failed call."""
        self._failures += 1
        self._last_failure = time.time()
        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker OPEN after {self._failures} failures")

    def can_proceed(self) -> bool:
        """Check if request can proceed."""
        if self._state == "closed":
            return True

        if self._state == "open":
            if time.time() - self._last_failure > self.recovery_timeout:
                self._state = "half-open"
                logger.info("Circuit breaker half-open, allowing test request")
                return True
            return False

        # half-open: allow one request to test
        return True


class LLMClient:
    """
    Unified LLM client with advanced features.

    Features:
    - Multiple provider support (OpenRouter, OpenAI, Anthropic, Google)
    - Automatic retry with exponential backoff
    - Rate limiting
    - Circuit breaker for fault tolerance
    - Request/response logging
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        env_config: EnvConfig | None = None,
    ):
        self._config = llm_config or get_config().llm
        self._env = env_config or get_env_config()
        self._model: BaseChatModel | None = None
        self._rate_limiter = RateLimiter(requests_per_minute=30)  # Conservative for free tier
        self._circuit_breaker = CircuitBreaker()
        self._init_model()

    def _init_model(self) -> None:
        """Initialize model based on provider."""
        provider = self._config.provider.lower()

        match provider:
            case "openrouter":
                self._init_openrouter()
            case "openai":
                self._init_openai()
            case "anthropic":
                self._init_anthropic()
            case "google":
                self._init_google()
            case _:
                raise ConfigurationError(f"Unknown provider: {provider}")

        logger.info(f"LLM initialized: {provider}/{self._config.model}")

    def _init_openrouter(self) -> None:
        """Initialize OpenRouter."""
        from langchain_openai import ChatOpenAI

        if api_key := self._env.openrouter_api_key:
            self._model = ChatOpenAI(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=self._config.timeout,
                api_key=api_key,
                base_url=self.OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/wwm-translator",
                    "X-Title": "WWM Translator",
                },
            )
        else:
            raise ConfigurationError("OPENROUTER_API_KEY not set in .env")

    def _init_openai(self) -> None:
        """Initialize OpenAI."""
        from langchain_openai import ChatOpenAI

        api_key = self._env.openai_api_key
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY not set")

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "timeout": self._config.timeout,
            "api_key": api_key,
        }

        if base_url := self._env.openai_api_base:
            kwargs["base_url"] = base_url

        self._model = ChatOpenAI(**kwargs)

    def _init_anthropic(self) -> None:
        """Initialize Anthropic."""
        from langchain_anthropic import ChatAnthropic

        if api_key := self._env.anthropic_api_key:
            self._model = ChatAnthropic(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=self._config.timeout,
                api_key=api_key,
            )
        else:
            raise ConfigurationError("ANTHROPIC_API_KEY not set")

    def _init_google(self) -> None:
        """Initialize Google Gemini."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        if api_key := self._env.google_api_key:
            self._model = ChatGoogleGenerativeAI(
                model=self._config.model,
                temperature=self._config.temperature,
                max_output_tokens=self._config.max_tokens,
                google_api_key=api_key,
            )
        else:
            raise ConfigurationError("GOOGLE_API_KEY not set")

    @property
    def model(self) -> BaseChatModel:
        """Get model instance."""
        if self._model is None:
            raise LLMClientError("Model not initialized")
        return self._model

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error for retry decision."""
        error_str = str(error).lower()

        # Rate limit errors - retry with backoff
        if any(x in error_str for x in ("rate", "limit", "429", "too many")):
            return ErrorType.RATE_LIMIT

        # Quota errors - don't retry
        if any(x in error_str for x in ("quota", "exceeded", "billing", "payment")):
            return ErrorType.QUOTA

        # Transient errors - retry
        if any(x in error_str for x in ("timeout", "connection", "502", "503", "504")):
            return ErrorType.TRANSIENT

        return ErrorType.PERMANENT

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((RateLimitError, TransientError, IncompleteResponseError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def translate_batch(
        self,
        texts: list[dict[str, str]],
        system_prompt: str,
        context_before: list[dict[str, str]] | None = None,
        context_after: list[dict[str, str]] | None = None,
    ) -> list[str]:
        """
        Translate a batch of texts with retry and rate limiting.

        Args:
            texts: List of dicts with 'english', 'original', 'id' keys
            system_prompt: System prompt with instructions
            context_before: Previous translated texts for reference
            context_after: Next texts (preview, do not translate)

        Returns:
            List of translations in same order
        """
        if not self._circuit_breaker.can_proceed():
            raise LLMClientError("Circuit breaker open - too many failures")

        await self._rate_limiter.acquire()

        user_message = self._build_message(
            texts,
            context_before or [],
            context_after or [],
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        try:
            start_time = time.time()
            response = await self.model.ainvoke(messages)
            elapsed = time.time() - start_time

            logger.debug(f"LLM response in {elapsed:.2f}s")

            result = self._parse_response(str(response.content), len(texts))
            self._circuit_breaker.record_success()

            return result

        except Exception as e:
            self._circuit_breaker.record_failure()
            error_type = self._classify_error(e)

            match error_type:
                case ErrorType.RATE_LIMIT:
                    logger.warning(f"Rate limit hit: {e}")
                    raise RateLimitError(str(e)) from e
                case ErrorType.QUOTA:
                    logger.error(f"Quota exceeded: {e}")
                    raise QuotaExceededError(str(e)) from e
                case ErrorType.TRANSIENT:
                    logger.warning(f"Transient error: {e}")
                    raise TransientError(str(e)) from e
                case _:
                    logger.error(f"Permanent error: {e}")
                    raise LLMClientError(str(e)) from e

    def translate_batch_sync(
        self,
        texts: list[dict[str, str]],
        system_prompt: str,
        context_before: list[dict[str, str]] | None = None,
        context_after: list[dict[str, str]] | None = None,
    ) -> list[str]:
        """Synchronous wrapper."""
        return asyncio.run(
            self.translate_batch(texts, system_prompt, context_before, context_after)
        )

    def _build_message(
        self,
        texts: list[dict[str, str]],
        context_before: list[dict[str, str]],
        context_after: list[dict[str, str]],
    ) -> str:
        """Build user message for translation request."""
        lines: list[str] = []

        if context_before:
            lines.append("=== REFERENCE (previously translated) ===")
            for item in context_before[-3:]:
                lines.append(f"EN: {item.get('english', '')}")
                if zh := item.get("original"):
                    lines.append(f"ZH: {zh}")
                if ru := item.get("translated"):
                    lines.append(f"RU: {ru}")
                lines.append("")

        lines.extend(("=== TRANSLATE THESE (EN -> RU) ===", ""))
        for i, item in enumerate(texts, 1):
            lines.extend((f"[{i}]", f"EN: {item.get('english', '')}"))
            if zh := item.get("original"):
                lines.append(f"ZH: {zh}")
            lines.append("")

        if context_after:
            lines.append("=== PREVIEW (next texts, DO NOT translate) ===")
            lines.extend(f"EN: {item.get('english', '')}" for item in context_after[:2])
            lines.append("")

        lines.extend(
            (
                "=== RESPONSE FORMAT ===",
                f"Return JSON array with exactly {len(texts)} Russian translations:",
                '["translation 1", "translation 2", ...]',
            )
        )
        return "\n".join(lines)

    def _parse_response(self, content: str, expected_count: int) -> list[str]:
        """Parse LLM response and extract translations."""
        content = content.strip()
        
        # Try to find JSON array in response
        start = content.find("[")
        end = content.rfind("]") + 1
        
        if start != -1 and end > start:
            try:
                result = json.loads(content[start:end])
                if isinstance(result, list):
                    return self._normalize_list(result, expected_count)
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse entire content as JSON
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return self._normalize_list(result, expected_count)
        except json.JSONDecodeError:
            pass
        
        # Last resort: split by newlines if looks like list
        lines = [line.strip().strip('"').strip("'") for line in content.split("\n") if line.strip()]
        if lines:
            return self._normalize_list(lines, expected_count)
        
        return [ErrorMarkers.PARSE_ERROR] * expected_count

    def _normalize_list(self, items: list, expected: int) -> list[str]:
        """Normalize result list to expected length."""
        result = [str(x) for x in items]

        if len(result) < expected:
            raise IncompleteResponseError(
                f"Got {len(result)} items, expected {expected} - retrying..."
            )
        elif len(result) > expected:
            result = result[:expected]

        return result


class PromptBuilder:
    """Translation prompt builder with caching."""

    __slots__ = ("_cache", "_game_context", "_rules_dir", "_translation_rules")

    def __init__(self, rules_dir: Path | str):
        self._rules_dir = Path(rules_dir)
        self._game_context: str = ""
        self._translation_rules: str = ""
        self._cache: dict[tuple, str] = {}

    def load(self) -> PromptBuilder:
        """Load rules from files."""
        context_file = self._rules_dir / "game_context.md"
        if context_file.exists():
            self._game_context = context_file.read_text(encoding="utf-8")

        rules_file = self._rules_dir / "translation_rules.md"
        if rules_file.exists():
            self._translation_rules = rules_file.read_text(encoding="utf-8")

        return self

    def build(
        self,
        source_lang: str = "en",
        original_lang: str = "zh_cn",
        target_lang: str = "ru",
    ) -> str:
        """Build system prompt with caching."""
        cache_key = (source_lang, original_lang, target_lang)

        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = self._build_prompt(source_lang, original_lang, target_lang)
        self._cache[cache_key] = prompt

        return prompt

    def _build_prompt(self, source_lang: str, original_lang: str, target_lang: str) -> str:
        """Build complete system prompt."""
        lang_names = {
            "zh_cn": "Chinese",
            "zh_tw": "Traditional Chinese",
            "en": "English",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
        }

        source = lang_names.get(source_lang, source_lang)
        original = lang_names.get(original_lang, original_lang)
        target = lang_names.get(target_lang, target_lang)

        sections = [
            self._role_section(source, original, target),
            "",
        ]

        if self._game_context:
            sections.extend(["## GAME CONTEXT", self._game_context, ""])

        if self._translation_rules:
            sections.extend(["## RULES", self._translation_rules, ""])

        sections.extend(
            [
                "## MULTI-LANGUAGE INPUT",
                f"- **EN** ({source}): Main text to translate",
                f"- **ZH** ({original}): Original for context/accuracy",
                "",
                "Use Chinese original to:",
                "- Verify meaning when English is ambiguous",
                "- Correctly transliterate Chinese names",
                "- Understand cultural/Wuxia references",
                "",
                "## LENGTH CONTROL",
                "If your translation is significantly longer (2x+) than English/Chinese:",
                "- Use shorter synonyms where possible",
                "- Remove filler words if meaning preserved",
                "- For UI/system messages: be concise",
                "- For dialogue/lore: keep full meaning, length is OK",
                "- NEVER sacrifice important meaning for brevity",
                "",
                "## OUTPUT",
                "Return JSON array of strings.",
                'Example: ["First", "Second"]',
                "Keep {tags} and formatting intact.",
            ]
        )

        return "\n".join(sections)

    def _role_section(self, source: str, original: str, target: str) -> str:
        """Build role description."""
        return f"""# ROLE: Professional Game Translator

You are an expert translator for the game **"Where Winds Meet"** (燕云十六声).

## ABOUT THE GAME
- Open-world action RPG set in ancient China (10th century)
- Wuxia (martial arts) genre with Qi cultivation, martial schools
- Political intrigue during Five Dynasties period
- Rich Chinese culture: poetry, philosophy, tea ceremonies

## YOUR TASK
Translate {source} text to {target}.
Use {original} original as reference when needed.

## KEY SKILLS
- Chinese martial arts (Wuxia) terminology
- Historical Chinese culture and philosophy
- Natural {target} that preserves atmosphere
- Consistent terminology throughout"""
