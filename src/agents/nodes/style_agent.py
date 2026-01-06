"""Style agent for analyzing code conventions and best practices."""

from ..prompts.style import PROMPT
from .base_agent import create_agent_runner

run = create_agent_runner(
    agent_name="style",
    prompt_template=PROMPT,
    check_type="style",
)
