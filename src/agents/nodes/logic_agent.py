"""Logic agent for analyzing code bugs and errors.

Uses the base agent factory for shared logic.
Supports per-repository configuration via ReviewerConfig.
"""

from ..prompts.logic import PROMPT
from .base_agent import create_agent_runner

AGENT_NAME = "logic"

run = create_agent_runner(
    agent_name=AGENT_NAME,
    prompt_template=PROMPT,
    check_type="logic",
)
