from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache


logger = logging.getLogger(__name__)

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not installed, using approximate token counting")


@dataclass
class TokenStats:
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def merge(self, other: TokenStats) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens

    def estimate_cost(self, price_input: float, price_output: float) -> float:
        """Estimate cost in USD (prices per 1M tokens)."""
        input_cost = (self.input_tokens / 1_000_000) * price_input
        output_cost = (self.output_tokens / 1_000_000) * price_output
        return input_cost + output_cost

    def format_stats(self, price_input: float = 0.0, price_output: float = 0.0) -> str:
        cost = self.estimate_cost(price_input, price_output)
        cost_str = f"${cost:.4f}" if cost > 0 else "FREE"
        return (
            f"Tokens: {self.total_tokens:,} "
            f"(in: {self.input_tokens:,}, out: {self.output_tokens:,}) | "
            f"Cost: {cost_str}"
        )


@dataclass
class CostConfig:
    """Cost configuration (USD per 1M tokens)."""

    price_input: float = 0.0
    price_output: float = 0.0

    @property
    def is_free(self) -> bool:
        return self.price_input == 0.0 and self.price_output == 0.0


class TokenCounter:
    """Token counter with tiktoken support, falls back to approximate counting."""

    MODEL_ENCODINGS = {
        "gpt-4": "cl100k_base",
        "gpt-4o": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "claude": "cl100k_base",
        "gemini": "cl100k_base",
        "grok": "cl100k_base",
        "llama": "cl100k_base",
    }

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoder = self._get_encoder(model)
        self._stats = TokenStats()

    @lru_cache(maxsize=10)
    def _get_encoder(self, model: str):
        if not TIKTOKEN_AVAILABLE:
            return None

        model_lower = model.lower()
        for prefix, encoding in self.MODEL_ENCODINGS.items():
            if prefix in model_lower:
                try:
                    return tiktoken.get_encoding(encoding)
                except Exception:
                    pass

        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0

        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass

        # Fallback: ~3 chars per token (conservative)
        return max(1, len(text) // 3)

    def count_messages(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            total += 4  # Message overhead
            if isinstance(msg, dict):
                total += self.count_tokens(msg.get("content", ""))
            else:
                total += self.count_tokens(str(msg))
        total += 2  # Priming tokens
        return total

    def record_usage(self, input_text: str, output_text: str) -> tuple[int, int]:
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)
        self._stats.add(input_tokens, output_tokens)
        return input_tokens, output_tokens

    def record_batch(
        self,
        system_prompt: str,
        user_message: str,
        response: str,
    ) -> tuple[int, int]:
        input_tokens = self.count_tokens(system_prompt) + self.count_tokens(user_message)
        output_tokens = self.count_tokens(response)
        self._stats.add(input_tokens, output_tokens)
        return input_tokens, output_tokens

    @property
    def stats(self) -> TokenStats:
        return self._stats

    def reset(self) -> None:
        self._stats = TokenStats()


_counter: TokenCounter | None = None


def get_token_counter(model: str = "gpt-4") -> TokenCounter:
    global _counter
    if _counter is None or _counter.model != model:
        _counter = TokenCounter(model)
    return _counter
