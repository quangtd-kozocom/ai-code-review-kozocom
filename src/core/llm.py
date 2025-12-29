"""LLM provider factory with OpenRouter, OpenAI, and Anthropic support."""

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from ..app.config import get_settings

log = structlog.get_logger()

_llm_instance: BaseChatModel | None = None


def get_llm(model: str | None = None) -> BaseChatModel:
    """
    Get the configured LLM instance.

    Priority order:
    1. OpenRouter (if OPENROUTER_API_KEY is set)
    2. OpenAI (if OPENAI_API_KEY is set)
    3. Anthropic (if ANTHROPIC_API_KEY is set)

    Args:
        model: Optional model name override. If None, uses default.

    Returns:
        Configured LLM instance.

    Raises:
        ValueError: If no API key is configured.
    """
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
    """
    Get an LLM configured for structured output.

    This wraps the LLM with `with_structured_output()` to ensure
    the response conforms to the given Pydantic schema.

    Args:
        output_schema: Pydantic model class defining the expected output.
        model: Optional model name override.

    Returns:
        LLM configured to return instances of output_schema.

    Example:
        >>> class Finding(BaseModel):
        ...     line: int
        ...     message: str
        >>> llm = get_structured_llm(Finding)
        >>> result = await llm.ainvoke("Find issues...")  # Returns Finding
    """
    llm = get_llm(model)
    return llm.with_structured_output(output_schema)


def _create_llm(model: str | None, settings) -> BaseChatModel:
    """
    Create an LLM instance based on configuration.

    Args:
        model: Model name to use, or None for default.
        settings: Application settings.

    Returns:
        Configured LLM instance.
    """
    # Priority 1: OpenRouter
    if settings.OPENROUTER_API_KEY:
        model_name = model or settings.OPENROUTER_DEFAULT_MODEL
        log.info("Using OpenRouter", model=model_name)
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=4096,
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
            temperature=0.1,
            max_tokens=4096,
        )

    # Priority 3: Anthropic
    if settings.ANTHROPIC_API_KEY:
        model_name = model or "claude-3-5-sonnet-20241022"
        log.info("Using Anthropic", model=model_name)
        return ChatAnthropic(
            model=model_name,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.1,
            max_tokens=4096,
        )

    raise ValueError(
        "No LLM API key configured. Set OPENROUTER_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY."
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def invoke_llm(llm: BaseChatModel, prompt: str) -> str:
    """
    Invoke LLM with retry logic.

    Args:
        llm: The LLM instance to invoke.
        prompt: The prompt to send.

    Returns:
        The LLM response content as string.
    """
    response = await llm.ainvoke(prompt)
    return response.content
