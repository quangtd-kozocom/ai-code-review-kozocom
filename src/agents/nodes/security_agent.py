"""Security agent for analyzing code vulnerabilities."""

from ..prompts.security import PROMPT
from .base_agent import create_agent_runner

run = create_agent_runner(
    agent_name="security",
    prompt_template=PROMPT,
    check_type="security",
)
