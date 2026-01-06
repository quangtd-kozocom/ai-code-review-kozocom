"""Security agent for analyzing code vulnerabilities.

Uses the base agent factory for shared logic.
Supports per-repository configuration via ReviewerConfig.
"""

from ..prompts.security import PROMPT
from .base_agent import create_agent_runner

AGENT_NAME = "security"

run = create_agent_runner(
    agent_name=AGENT_NAME,
    prompt_template=PROMPT,
    check_type="security",
)
