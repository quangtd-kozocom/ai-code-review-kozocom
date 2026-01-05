# 06 - Agent Integration

## 🎯 Overview

Document này mô tả cách integrate ConfigService vào agents.

---

## 📦 Update GraphState

### File: `src/agents/state.py`

```python
"""
Graph state for LangGraph workflow.
"""

from typing import TypedDict
from pydantic import BaseModel

from ..core.config import ReviewerConfig  # ADD THIS IMPORT


class FileChange(BaseModel):
    """Represents a changed file in a PR."""
    filename: str
    status: str
    patch: str | None = None
    language: str | None = None


class ReviewComment(BaseModel):
    """A review comment to post."""
    file: str
    line: int
    severity: str
    category: str
    message: str
    suggestion: str | None = None
    confidence: float
    agent: str


class PRContext(BaseModel):
    """PR context information."""
    owner: str
    repo: str
    pr_number: int
    installation_id: int


class GraphState(TypedDict):
    """State passed through the workflow."""

    # Input
    context: PRContext

    # Configuration - NEW
    repo_config: ReviewerConfig

    # Extracted
    files: list[FileChange]

    # Agent outputs
    security_comments: list[ReviewComment]
    logic_comments: list[ReviewComment]
    style_comments: list[ReviewComment]

    # Aggregated
    final_comments: list[ReviewComment]
    summary: str
```

---

## 📦 Update Context Extractor

### File: `src/agents/nodes/context_extractor.py`

```python
"""
Context extractor node - loads config and PR files.
"""

import structlog
from ..state import GraphState, FileChange, PRContext
from ...app.services.github import GitHubService
from ...core.config import ConfigService, ReviewerConfig
from ...core.database import get_db_pool

log = structlog.get_logger()


async def run(state: GraphState) -> dict:
    """
    Extract context: load config and PR files.

    Returns:
        dict with 'files' and 'repo_config'
    """
    ctx: PRContext = state["context"]

    # Initialize services
    github = GitHubService(ctx.installation_id)
    db_pool = await get_db_pool()

    # Create config service
    from ...core.config.factory import create_config_service
    config_service = await create_config_service(
        github=github,
        redis_url=get_settings().UPSTASH_REDIS_URL,
        db_pool=db_pool,
    )

    # Load configuration
    config = await config_service.get_config(ctx.owner, ctx.repo)

    log.info(
        "Config loaded",
        owner=ctx.owner,
        repo=ctx.repo,
        profile=config.reviews.profile,
        ignore_patterns=len(config.ignore),
        path_instructions=len(config.reviews.path_instructions),
    )

    # Check if should auto-review
    pr_info = await github.get_pr(ctx.owner, ctx.repo, ctx.pr_number)

    if not config.should_auto_review(
        title=pr_info["title"],
        author=pr_info["user"]["login"],
        base_branch=pr_info["base"]["ref"],
        is_draft=pr_info.get("draft", False),
    ):
        log.info("PR skipped by auto-review settings", pr=ctx.pr_number)
        return {
            "files": [],
            "repo_config": config,
        }

    # Get PR files
    raw_files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    # Filter and convert files
    files: list[FileChange] = []
    for f in raw_files:
        filename = f["filename"]

        # Apply ignore patterns
        if config.should_ignore(filename):
            log.debug("File ignored by config", file=filename)
            continue

        files.append(FileChange(
            filename=filename,
            status=f["status"],
            patch=f.get("patch"),
            language=_detect_language(filename),
        ))

    log.info(
        "Context extracted",
        total_files=len(raw_files),
        filtered_files=len(files),
    )

    return {
        "files": files,
        "repo_config": config,
    }


def _detect_language(filename: str) -> str | None:
    """Detect language from filename."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }
    for ext, lang in ext_map.items():
        if filename.endswith(ext):
            return lang
    return None
```

---

## 📦 Update Security Agent

### File: `src/agents/nodes/security_agent.py`

```python
"""
Security agent - detects security vulnerabilities.
"""

import asyncio
import structlog

from ..state import GraphState, ReviewComment, FileChange
from ..models import AgentFindings
from ..prompts.security import PROMPT
from ...core.config import ReviewerConfig
from ...core.llm import get_structured_llm

log = structlog.get_logger()

MAX_CONCURRENT = 3


async def run(state: GraphState) -> dict:
    """
    Analyze files for security issues.

    Uses config for:
    - confidence_threshold
    - max_comments_per_file
    - path_instructions
    """
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    files = [f for f in state["files"] if f.patch]

    # Check if security agent is enabled
    if "security" not in config.reviews.agents:
        log.info("Security agent disabled by config")
        return {"security_comments": []}

    log.info("Security agent started", files=len(files))

    # Get effective thresholds from config
    threshold = config.get_threshold()
    max_comments = config.get_max_comments()

    structured_llm = get_structured_llm(AgentFindings)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def process_file(file: FileChange) -> list[ReviewComment]:
        """Process single file with config-aware prompting."""

        # Get path-specific instructions
        extra_instructions = config.get_path_instructions(file.filename)

        # Build prompt with extra instructions
        prompt = _build_prompt(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
            extra_instructions=extra_instructions,
        )

        try:
            async with semaphore:
                result = await structured_llm.ainvoke(prompt)

            # Filter by configured threshold
            comments = []
            for finding in result.findings:
                if finding.confidence >= threshold:
                    comments.append(ReviewComment(
                        file=file.filename,
                        line=finding.line,
                        severity=finding.severity,
                        category=finding.category or "security",
                        message=finding.message,
                        suggestion=finding.suggestion,
                        confidence=finding.confidence,
                        agent="security",
                    ))

            # Limit comments per file
            return comments[:max_comments]

        except Exception as e:
            log.error("Security analysis failed", file=file.filename, error=str(e))
            return []

    # Process all files
    tasks = [process_file(f) for f in files]
    results = await asyncio.gather(*tasks)

    all_comments = []
    for comments in results:
        all_comments.extend(comments)

    log.info("Security agent complete", comments=len(all_comments))

    return {"security_comments": all_comments}


def _build_prompt(
    filename: str,
    language: str,
    diff: str,
    extra_instructions: list[str],
) -> str:
    """Build prompt with optional extra instructions."""

    base_prompt = PROMPT.format(
        filename=filename,
        language=language,
        diff=diff,
    )

    if extra_instructions:
        instructions_text = "\n".join(f"- {i}" for i in extra_instructions)
        return f"""{base_prompt}

## Repository-Specific Guidelines

The following additional guidelines apply to this file:

{instructions_text}

Apply these guidelines in addition to the standard security checks.
"""

    return base_prompt
```

---

## 📦 Apply Same Pattern to Other Agents

### Logic Agent Template

```python
# src/agents/nodes/logic_agent.py

async def run(state: GraphState) -> dict:
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())

    # Check if enabled
    if "logic" not in config.reviews.agents:
        return {"logic_comments": []}

    # Get thresholds
    threshold = config.get_threshold()
    max_comments = config.get_max_comments()

    # ... rest same pattern as security_agent
```

### Style Agent Template

```python
# src/agents/nodes/style_agent.py

async def run(state: GraphState) -> dict:
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())

    if "style" not in config.reviews.agents:
        return {"style_comments": []}

    # ... rest same pattern
```

---

## 📦 Update Aggregator

### File: `src/agents/nodes/aggregator.py`

```python
"""
Aggregator node - combines and sorts comments.
"""

from ..state import GraphState, ReviewComment
from ...core.config import ReviewerConfig

# Severity ordering
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}


async def run(state: GraphState) -> dict:
    """Aggregate comments with config-aware limits."""

    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    max_per_file = config.get_max_comments()

    # Collect all comments
    all_comments: list[ReviewComment] = []
    all_comments.extend(state.get("security_comments", []))
    all_comments.extend(state.get("logic_comments", []))
    all_comments.extend(state.get("style_comments", []))

    # Deduplicate by (file, line, message)
    seen = set()
    unique = []
    for c in all_comments:
        key = (c.file, c.line, c.message[:50])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Sort by severity, then confidence
    unique.sort(key=lambda c: (
        SEVERITY_ORDER.get(c.severity, 99),
        -c.confidence,
    ))

    # Limit per file
    by_file: dict[str, list[ReviewComment]] = {}
    for c in unique:
        if c.file not in by_file:
            by_file[c.file] = []
        if len(by_file[c.file]) < max_per_file:
            by_file[c.file].append(c)

    final = []
    for comments in by_file.values():
        final.extend(comments)

    # Generate summary
    summary = _generate_summary(final, config.language)

    return {
        "final_comments": final,
        "summary": summary,
    }


def _generate_summary(comments: list[ReviewComment], language: str) -> str:
    """Generate summary in configured language."""

    by_severity = {}
    for c in comments:
        by_severity.setdefault(c.severity, 0)
        by_severity[c.severity] += 1

    if language == "vi":
        return f"""## 📊 Tóm Tắt

| Mức độ | Số lượng |
|--------|----------|
| 🔴 Critical | {by_severity.get('critical', 0)} |
| 🟡 Warning | {by_severity.get('warning', 0)} |
| 🔵 Info | {by_severity.get('info', 0)} |
| 💡 Suggestion | {by_severity.get('suggestion', 0)} |
"""

    return f"""## 📊 Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | {by_severity.get('critical', 0)} |
| 🟡 Warning | {by_severity.get('warning', 0)} |
| 🔵 Info | {by_severity.get('info', 0)} |
| 💡 Suggestion | {by_severity.get('suggestion', 0)} |
"""
```

---

## ✅ Integration Checklist

- [ ] Add `repo_config: ReviewerConfig` to GraphState
- [ ] Update context_extractor to load config
- [ ] Update context_extractor to filter ignored files
- [ ] Update security_agent to use config
- [ ] Update logic_agent to use config
- [ ] Update style_agent to use config
- [ ] Update aggregator to respect limits
- [ ] Add language support in summary
