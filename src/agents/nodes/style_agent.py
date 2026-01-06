"""Style agent for analyzing code conventions and best practices.

Uses the base agent factory for shared logic.
Supports per-repository configuration via ReviewerConfig.
"""

from ..prompts.style import PROMPT
from .base_agent import create_agent_runner

AGENT_NAME = "style"

run = create_agent_runner(
    agent_name=AGENT_NAME,
    prompt_template=PROMPT,
    check_type="style",
)
