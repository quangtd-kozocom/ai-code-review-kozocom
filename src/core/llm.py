"""LLM provider factory with retry support for transient errors."""

from functools import lru_cache
from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from openai import AuthenticationError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..app.config import get_settings
from .constants import DEFAULT_LLM_MAX_TOKENS, DEFAULT_LLM_TEMPERATURE

__all__ = ["get_llm", "get_structured_llm", "invoke_with_retry"]

log = structlog.get_logger()

LLM_MAX_RETRIES = 3


def _is_openrouter_transient(exc: BaseException) -> bool:
    """Check if exception is OpenRouter's transient 401 'User not found' error."""
    return isinstance(exc, AuthenticationError) and "User not found" in str(exc)


@retry(
    retry=retry_if_exception(_is_openrouter_transient),
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=lambda rs: log.warning("llm.retry_401", attempt=rs.attempt_number),
)
async def invoke_with_retry(llm: BaseChatModel, prompt: str) -> Any:
    """Invoke LLM with retry for OpenRouter transient 401 errors."""
    return await llm.ainvoke(prompt)


@lru_cache(maxsize=8)
def _create_llm(model_name: str, provider: str) -> BaseChatModel:
    """Create and cache LLM instance."""
    settings = get_settings()
    common = {"temperature": DEFAULT_LLM_TEMPERATURE, "max_retries": LLM_MAX_RETRIES}

    match provider:
        case "openrouter":
            log.info("llm.create", provider="openrouter", model=model_name)
            return ChatOpenAI(
                model=model_name,
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                max_tokens=DEFAULT_LLM_MAX_TOKENS,
                default_headers={
                    "HTTP-Referer": settings.APP_URL or "https://ai-code-reviewer.local",
                    "X-Title": "AI Code Reviewer",
                },
                **common,
            )
        case "openai":
            log.info("llm.create", provider="openai", model=model_name)
            return ChatOpenAI(
                model=model_name,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=DEFAULT_LLM_MAX_TOKENS,
                **common,
            )
        case "anthropic":
            log.info("llm.create", provider="anthropic", model=model_name)
            return ChatAnthropic(
                model=model_name,
                api_key=settings.ANTHROPIC_API_KEY,
                max_tokens=DEFAULT_LLM_MAX_TOKENS,
                **common,
            )
        case "google":
            log.info("llm.create", provider="google", model=model_name)
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                max_output_tokens=DEFAULT_LLM_MAX_TOKENS,
                **common,
            )
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm(model: str | None = None) -> BaseChatModel:
    """Get configured LLM instance. Priority: OpenRouter -> OpenAI -> Anthropic -> Google."""
    settings = get_settings()

    providers = [
        (settings.OPENROUTER_API_KEY, settings.OPENROUTER_DEFAULT_MODEL, "openrouter"),
        (settings.OPENAI_API_KEY, "gpt-4o-mini", "openai"),
        (settings.ANTHROPIC_API_KEY, "claude-3-5-sonnet-20241022", "anthropic"),
        (settings.GOOGLE_API_KEY, settings.GOOGLE_DEFAULT_MODEL, "google"),
    ]

    for api_key, default_model, provider in providers:
        if api_key:
            return _create_llm(model or default_model, provider)

    raise ValueError("No LLM API key configured.")


def get_structured_llm[T: BaseModel](schema: type[T], model: str | None = None) -> BaseChatModel:
    """Get LLM configured for structured output."""
    return get_llm(model).with_structured_output(schema)
