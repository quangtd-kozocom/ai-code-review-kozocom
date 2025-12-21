import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..app.config import get_settings

log = structlog.get_logger()

_llm_instance: BaseChatModel | None = None


def get_llm(model: str | None = None) -> BaseChatModel:
    """Get the configured LLM instance."""
    global _llm_instance

    settings = get_settings()

    # If specific model requested, don't cache
    if model:
        return _create_llm(model, settings)

    # Return cached instance
    if _llm_instance is None:
        _llm_instance = _create_llm(None, settings)

    return _llm_instance


def _create_llm(model: str | None, settings) -> BaseChatModel:
    """Create an LLM instance based on configuration."""
    # Default to OpenAI if available
    if settings.OPENAI_API_KEY:
        model_name = model or "gpt-4o"
        log.info("Using OpenAI", model=model_name)
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
            max_tokens=4096,
        )

    # Fallback to Anthropic
    if settings.ANTHROPIC_API_KEY:
        model_name = model or "claude-3-5-sonnet-20241022"
        log.info("Using Anthropic", model=model_name)
        return ChatAnthropic(
            model=model_name,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.1,
            max_tokens=4096,
        )

    raise ValueError("No LLM API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def invoke_llm(llm: BaseChatModel, prompt: str) -> str:
    """Invoke LLM with retry logic."""
    response = await llm.ainvoke(prompt)
    return response.content
