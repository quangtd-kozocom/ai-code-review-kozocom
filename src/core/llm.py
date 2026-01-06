"""LLM provider factory with OpenRouter, OpenAI, and Anthropic support."""

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from ..app.config import Settings, get_settings
from .constants import DEFAULT_LLM_MAX_TOKENS, DEFAULT_LLM_TEMPERATURE

__all__ = ["get_llm", "get_structured_llm"]

log = structlog.get_logger()

_llm_instance: BaseChatModel | None = None


def get_llm(model: str | None = None) -> BaseChatModel:
    """Get configured LLM instance. Tries OpenRouter -> OpenAI -> Anthropic."""
    global _llm_instance

    settings = get_settings()

    # If specific model requested, don't cache
    if model:
        return _create_llm(model, settings)

    # Return cached instance
    if _llm_instance is None:
        _llm_instance = _create_llm(None, settings)

    return _llm_instance


def get_structured_llm[T: BaseModel](
    output_schema: type[T], model: str | None = None
) -> BaseChatModel:
    """Get LLM configured for structured output with the given Pydantic schema."""
    llm = get_llm(model)
    return llm.with_structured_output(output_schema)


def _create_llm(model: str | None, settings: Settings) -> BaseChatModel:
    """Create LLM instance based on available API keys."""
    # Priority 1: OpenRouter
    if settings.OPENROUTER_API_KEY:
        model_name = model or settings.OPENROUTER_DEFAULT_MODEL
        log.info("Using OpenRouter", model=model_name)
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=DEFAULT_LLM_TEMPERATURE,
            max_tokens=DEFAULT_LLM_MAX_TOKENS,
            default_headers={
                "HTTP-Referer": settings.APP_URL or "https://ai-code-reviewer.local",
                "X-Title": "AI Code Reviewer",
            },
        )

    # Priority 2: OpenAI
    if settings.OPENAI_API_KEY:
        model_name = model or "gpt-4o-mini"
        log.info("Using OpenAI", model=model_name)
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=DEFAULT_LLM_TEMPERATURE,
            max_tokens=DEFAULT_LLM_MAX_TOKENS,
        )

    # Priority 3: Anthropic
    if settings.ANTHROPIC_API_KEY:
        model_name = model or "claude-3-5-sonnet-20241022"
        log.info("Using Anthropic", model=model_name)
        return ChatAnthropic(
            model=model_name,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=DEFAULT_LLM_TEMPERATURE,
            max_tokens=DEFAULT_LLM_MAX_TOKENS,
        )

    raise ValueError(
        "No LLM API key configured. Set OPENROUTER_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY."
    )
