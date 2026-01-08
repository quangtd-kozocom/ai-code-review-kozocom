"""Smart router node - Content-aware routing based on code analysis."""

import asyncio
from typing import Literal

import structlog
from pydantic import BaseModel, Field

from ...core.llm import get_structured_llm
from ..prompts.router import PROMPT
from ..state import GraphState

log = structlog.get_logger()

type AgentType = Literal["security", "style", "logic"]

SKIP_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".lock", ".md", ".txt", ".csv"}
TEST_PATTERNS = {"test_", "_test.py", "tests/", "spec/", ".spec.", ".test."}


class SecuritySignals(BaseModel):
    has_user_input: bool = Field(description="Handles user input or external data")
    has_db_operations: bool = Field(description="Database queries or ORM operations")
    has_auth_logic: bool = Field(description="Authentication or authorization code")
    has_external_calls: bool = Field(description="HTTP requests, subprocess, eval/exec")
    has_file_operations: bool = Field(description="File I/O with dynamic paths")
    has_crypto: bool = Field(description="Cryptography or secrets handling")


class LogicSignals(BaseModel):
    has_complex_conditions: bool = Field(description="Nested or complex conditionals")
    has_loops: bool = Field(description="Loop operations with logic")
    has_error_handling: bool = Field(description="Try/except or error handling")
    has_data_transforms: bool = Field(description="Data transformations or mappings")
    has_null_handling: bool = Field(description="None/null checks present or missing")


class StyleSignals(BaseModel):
    has_magic_values: bool = Field(description="Hardcoded numbers or strings")
    has_naming_issues: bool = Field(description="Poor naming conventions")
    has_missing_types: bool = Field(description="Missing type annotations")
    has_long_functions: bool = Field(description="Long or complex functions")


class FileAnalysis(BaseModel):
    file: str
    security_signals: SecuritySignals
    logic_signals: LogicSignals
    style_signals: StyleSignals
    agents: list[AgentType] = Field(description="Agents to run based on detected signals")
    reasoning: str = Field(description="Brief explanation linking signals to decision")


class RouterOutput(BaseModel):
    analyses: list[FileAnalysis] = Field(default_factory=list)


def _is_test_file(filename: str) -> bool:
    filename_lower = filename.lower()
    return any(pattern in filename_lower for pattern in TEST_PATTERNS)


def _is_skip_file(filename: str) -> bool:
    return any(filename.endswith(ext) for ext in SKIP_EXTENSIONS)


def _format_files_for_prompt(files: list) -> str:
    parts = []
    for f in files:
        if not f.patch:
            continue
        truncated_patch = f.patch[:2000] if len(f.patch) > 2000 else f.patch
        parts.append(f"### {f.filename}\n```\n{truncated_patch}\n```")
    return "\n\n".join(parts)


def _signals_to_agents(analysis: FileAnalysis, is_test: bool) -> list[str]:
    """Derive agents from signals as fallback validation."""
    agents = []
    sec = analysis.security_signals
    logic = analysis.logic_signals
    style = analysis.style_signals

    if any([sec.has_user_input, sec.has_db_operations, sec.has_auth_logic,
            sec.has_external_calls, sec.has_file_operations, sec.has_crypto]):
        agents.append("security")

    if any([logic.has_complex_conditions, logic.has_loops, logic.has_error_handling,
            logic.has_data_transforms, logic.has_null_handling]):
        agents.append("logic")

    if not is_test and any([style.has_magic_values, style.has_naming_issues,
                            style.has_missing_types, style.has_long_functions]):
        agents.append("style")

    return agents if agents else ["logic"]


async def run(state: GraphState) -> dict:
    """Content-aware routing based on code signal analysis."""
    files = [f for f in state["files"] if f.patch]

    if not files:
        log.info("router.no_files")
        return {"routing_decisions": {}}

    files_to_route = []
    routing_decisions: dict[str, list[str]] = {}

    for f in files:
        if _is_skip_file(f.filename):
            routing_decisions[f.filename] = []
            log.debug("router.skip", file=f.filename, reason="config_file")
            continue
        files_to_route.append(f)

    if not files_to_route:
        return {"routing_decisions": routing_decisions}

    files_content = _format_files_for_prompt(files_to_route[:15])
    prompt = PROMPT.format(files_content=files_content)

    try:
        llm = get_structured_llm(RouterOutput)
        result = await asyncio.wait_for(llm.ainvoke(prompt), timeout=30.0)

        for analysis in result.analyses:
            is_test = _is_test_file(analysis.file)
            agents = analysis.agents or _signals_to_agents(analysis, is_test)

            if is_test and "style" in agents:
                agents = [a for a in agents if a != "style"]

            routing_decisions[analysis.file] = list(agents)
            log.info(
                "router.decision",
                file=analysis.file,
                agents=agents,
                security_signals=analysis.security_signals.model_dump(),
                logic_signals=analysis.logic_signals.model_dump(),
                reasoning=analysis.reasoning,
            )

        for f in files_to_route:
            if f.filename not in routing_decisions:
                routing_decisions[f.filename] = ["security", "style", "logic"]
                log.warning("router.missing_analysis", file=f.filename)

    except asyncio.TimeoutError:
        log.warning("router.timeout")
        for f in files_to_route:
            routing_decisions[f.filename] = ["security", "style", "logic"]
    except Exception as e:
        log.error("router.error", error=str(e))
        for f in files_to_route:
            routing_decisions[f.filename] = ["security", "style", "logic"]

    log.info("router.completed", total_files=len(files), routed=len(routing_decisions))
    return {"routing_decisions": routing_decisions}
