"""Logic agent for analyzing code bugs and errors."""

from ..prompts.logic import PROMPT
from .base_agent import create_agent_runner

run = create_agent_runner(
    agent_name="logic",
    prompt_template=PROMPT,
    check_type="logic",
)
