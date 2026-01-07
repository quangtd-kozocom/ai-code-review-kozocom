# 🤖 Parallel Agent Design Patterns

> Thiết kế Multi-Agent System cho Code Review với khả năng mở rộng và nhúng agents mới.

---

## 1. Current Architecture Analysis

### 1.1 Existing Flow

```python
# Current graph.py
def create_graph() -> StateGraph:
    g = StateGraph(GraphState)

    # Static node definition
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)

    # Static edges
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")
```

**Limitations:**

1. ❌ Agents được hardcode - khó thêm/bỏ agents
2. ❌ Tất cả agents chạy cho mọi file
3. ❌ Không có conditional routing
4. ❌ Không có dynamic agent selection

### 1.2 Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Dynamic Agent Orchestration                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │   File Context   │                                                       │
│  │   (language,     │                                                       │
│  │    type, size)   │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────┐    ┌─────────────────────────────────────────────┐   │
│  │  Agent Router    │───▶│  Dynamic Agent Selection                    │   │
│  │                  │    │                                              │   │
│  │  Rules:          │    │  Python file → [security, style, logic]     │   │
│  │  - By language   │    │  Test file   → [test_quality]               │   │
│  │  - By file type  │    │  Config file → [config_validator]           │   │
│  │  - By content    │    │  SQL file    → [sql_injection, style]       │   │
│  │  - By config     │    │                                              │   │
│  └──────────────────┘    └─────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Agent Pool (Pluggable)                        │   │
│  │                                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Security │ │  Style   │ │  Logic   │ │   Test   │ │  Perf    │  │   │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │                                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │   │
│  │  │   SQL    │ │  Config  │ │   API    │ │ Custom   │ ...          │   │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │              │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Registry Pattern

### 2.1 Agent Interface

```python
# agents/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..state import FileChange, ReviewComment

class AgentCapability(BaseModel):
    """Describes what an agent can analyze."""
    languages: list[str] = []  # ["python", "javascript", "*"]
    file_patterns: list[str] = []  # ["*_test.py", "*.sql"]
    categories: list[str] = []  # ["security", "style"]

class AgentMetadata(BaseModel):
    """Agent registration metadata."""
    name: str
    description: str
    version: str
    capability: AgentCapability
    priority: int = 100  # Lower = runs first
    enabled: bool = True

class BaseReviewAgent(ABC):
    """Abstract base class for all review agents."""

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Return agent metadata for registration."""
        pass

    @abstractmethod
    async def analyze(
        self,
        file: "FileChange",
        context: dict,
    ) -> list["ReviewComment"]:
        """Analyze a file and return findings."""
        pass

    def should_run(self, file: "FileChange") -> bool:
        """Check if this agent should run for the given file."""
        cap = self.metadata.capability

        # Check language match
        if cap.languages and "*" not in cap.languages:
            if file.language and file.language not in cap.languages:
                return False

        # Check file pattern match
        if cap.file_patterns:
            from fnmatch import fnmatch
            if not any(fnmatch(file.filename, p) for p in cap.file_patterns):
                return False

        return True
```

### 2.2 Agent Registry

```python
# agents/registry.py
from typing import Type
import structlog

from .base import BaseReviewAgent, AgentMetadata

log = structlog.get_logger()

class AgentRegistry:
    """Central registry for all available agents."""

    _instance: "AgentRegistry | None" = None

    def __init__(self):
        self._agents: dict[str, BaseReviewAgent] = {}

    @classmethod
    def get_instance(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, agent: BaseReviewAgent) -> None:
        """Register an agent."""
        name = agent.metadata.name
        if name in self._agents:
            log.warning("agent.overwrite", name=name)
        self._agents[name] = agent
        log.info("agent.registered", name=name, version=agent.metadata.version)

    def register_class(self, agent_class: Type[BaseReviewAgent]) -> Type[BaseReviewAgent]:
        """Decorator to register an agent class."""
        self.register(agent_class())
        return agent_class

    def get_agent(self, name: str) -> BaseReviewAgent | None:
        """Get a registered agent by name."""
        return self._agents.get(name)

    def get_agents_for_file(
        self,
        file: "FileChange",
        enabled_only: bool = True,
    ) -> list[BaseReviewAgent]:
        """Get all agents that should run for a file."""
        agents = []
        for agent in self._agents.values():
            if enabled_only and not agent.metadata.enabled:
                continue
            if agent.should_run(file):
                agents.append(agent)

        # Sort by priority
        return sorted(agents, key=lambda a: a.metadata.priority)

    def list_agents(self) -> list[AgentMetadata]:
        """List all registered agents."""
        return [a.metadata for a in self._agents.values()]

# Global instance
registry = AgentRegistry.get_instance()
```

### 2.3 Agent Implementations

```python
# agents/security_agent.py
from .base import BaseReviewAgent, AgentMetadata, AgentCapability
from .registry import registry
from ..state import FileChange, ReviewComment

@registry.register_class
class SecurityAgent(BaseReviewAgent):
    """Agent for security vulnerability detection."""

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="security",
            description="Detects security vulnerabilities",
            version="1.0.0",
            capability=AgentCapability(
                languages=["python", "javascript", "typescript", "java", "go"],
                categories=["security"],
            ),
            priority=10,  # Run early
        )

    async def analyze(
        self,
        file: FileChange,
        context: dict,
    ) -> list[ReviewComment]:
        # Implementation using LLM
        llm = get_structured_llm(SecurityFindings)
        prompt = self._build_prompt(file)
        result = await llm.ainvoke(prompt)
        return self._convert_to_comments(result, file)

# agents/test_quality_agent.py
@registry.register_class
class TestQualityAgent(BaseReviewAgent):
    """Agent for test code quality analysis."""

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="test_quality",
            description="Analyzes test code quality and coverage",
            version="1.0.0",
            capability=AgentCapability(
                languages=["python", "javascript", "typescript"],
                file_patterns=["*_test.py", "test_*.py", "*.test.ts", "*.spec.ts"],
                categories=["testing"],
            ),
            priority=50,
        )

    async def analyze(self, file: FileChange, context: dict) -> list[ReviewComment]:
        # Test-specific analysis
        ...

# agents/sql_injection_agent.py
@registry.register_class
class SqlInjectionAgent(BaseReviewAgent):
    """Agent for SQL injection detection."""

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="sql_injection",
            description="Detects potential SQL injection vulnerabilities",
            version="1.0.0",
            capability=AgentCapability(
                languages=["python", "php", "java"],
                file_patterns=["*.py", "*.php", "*.java"],
                categories=["security"],
            ),
            priority=5,  # High priority
        )

    def should_run(self, file: FileChange) -> bool:
        """Only run if file contains SQL-related code."""
        if not super().should_run(file):
            return False

        # Check for SQL keywords in diff
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "execute", "cursor"]
        return any(kw in file.patch.upper() for kw in sql_keywords)

    async def analyze(self, file: FileChange, context: dict) -> list[ReviewComment]:
        ...
```

---

## 3. Dynamic Routing với LangGraph

### 3.1 Conditional Edge Router

```python
# agents/router.py
from langgraph.graph import Send
from .registry import registry
from ..state import GraphState, FileChange

def route_files_to_agents(state: GraphState) -> list[Send]:
    """
    Dynamic router that decides which agents to run for each file.
    Returns Send objects for LangGraph parallel execution.
    """
    sends = []
    files = state["files"]
    config = state["repo_config"]

    for file in files:
        # Get agents for this file
        agents = registry.get_agents_for_file(file)

        # Filter by config
        enabled_agents = [
            a for a in agents
            if config.is_agent_enabled(a.metadata.name)
        ]

        if not enabled_agents:
            continue

        # Create Send for this file with its agents
        sends.append(Send(
            "process_file_with_agents",
            {
                "file": file,
                "agent_names": [a.metadata.name for a in enabled_agents],
                "context": state["context"],
                "repo_config": config,
            }
        ))

    return sends

async def process_file_with_agents(state: dict) -> dict:
    """Process a single file with its designated agents."""
    file = state["file"]
    agent_names = state["agent_names"]
    context = state["context"]

    all_comments = []

    for agent_name in agent_names:
        agent = registry.get_agent(agent_name)
        if agent:
            try:
                comments = await agent.analyze(file, context)
                all_comments.extend(comments)
            except Exception as e:
                log.error("agent.error", agent=agent_name, file=file.filename, error=str(e))

    return {"file_comments": all_comments}
```

### 3.2 Updated Graph

```python
# agents/dynamic_graph.py
from langgraph.graph import StateGraph, END

def create_dynamic_review_graph() -> StateGraph:
    """Create graph with dynamic agent routing."""

    g = StateGraph(DynamicGraphState)

    # Core nodes
    g.add_node("acknowledge", acknowledge)
    g.add_node("extract", extract_context)
    g.add_node("process_file_with_agents", process_file_with_agents)
    g.add_node("post_comments", post_comments)
    g.add_node("summarize", generate_summary)

    # Entry
    g.set_entry_point("acknowledge")

    # Flow
    g.add_edge("acknowledge", "extract")

    # Dynamic routing: each file -> its applicable agents
    g.add_conditional_edges(
        "extract",
        route_files_to_agents,  # Returns list[Send]
    )

    # After file processing, post immediately
    g.add_edge("process_file_with_agents", "post_comments")

    # All branches join at summarize
    g.add_edge("post_comments", "summarize")
    g.add_edge("summarize", END)

    return g.compile()
```

---

## 4. Agent Composition Patterns

### 4.1 Pipeline Agents (Sequential)

```python
class PipelineAgent(BaseReviewAgent):
    """
    Composes multiple sub-agents in a pipeline.
    Output of one feeds into next.
    """

    def __init__(self, agents: list[BaseReviewAgent]):
        self._agents = agents

    async def analyze(self, file: FileChange, context: dict) -> list[ReviewComment]:
        enriched_context = context.copy()
        all_comments = []

        for agent in self._agents:
            # Each agent can enrich context for next
            comments = await agent.analyze(file, enriched_context)
            all_comments.extend(comments)

            # Pass comments to next agent
            enriched_context["previous_findings"] = all_comments

        return all_comments

# Usage:
security_pipeline = PipelineAgent([
    SastAnalyzer(),      # Static analysis first
    SecurityLlmAgent(),  # LLM for deeper analysis
    FalsePositiveFilter(),  # Filter out noise
])
```

### 4.2 Voting Agents (Ensemble)

```python
class VotingAgent(BaseReviewAgent):
    """
    Runs multiple agents and aggregates by voting.
    Only reports issues found by majority.
    """

    def __init__(
        self,
        agents: list[BaseReviewAgent],
        threshold: float = 0.5,
    ):
        self._agents = agents
        self._threshold = threshold

    async def analyze(self, file: FileChange, context: dict) -> list[ReviewComment]:
        # Run all agents in parallel
        results = await asyncio.gather(*[
            a.analyze(file, context) for a in self._agents
        ])

        # Group by (line, category) and vote
        votes: dict[tuple[int, str], list[ReviewComment]] = defaultdict(list)
        for agent_comments in results:
            for comment in agent_comments:
                key = (comment.line, comment.category)
                votes[key].append(comment)

        # Keep only majority votes
        final_comments = []
        for key, comments in votes.items():
            vote_ratio = len(comments) / len(self._agents)
            if vote_ratio >= self._threshold:
                # Take the one with highest confidence
                best = max(comments, key=lambda c: c.confidence)
                final_comments.append(best)

        return final_comments
```

### 4.3 Specialist + Generalist Pattern

```python
class SpecialistGeneralistAgent(BaseReviewAgent):
    """
    Uses specialist agent if applicable, falls back to generalist.
    """

    def __init__(
        self,
        specialists: dict[str, BaseReviewAgent],  # language -> agent
        generalist: BaseReviewAgent,
    ):
        self._specialists = specialists
        self._generalist = generalist

    async def analyze(self, file: FileChange, context: dict) -> list[ReviewComment]:
        # Try specialist first
        if file.language in self._specialists:
            agent = self._specialists[file.language]
            return await agent.analyze(file, context)

        # Fall back to generalist
        return await self._generalist.analyze(file, context)

# Usage:
security_agent = SpecialistGeneralistAgent(
    specialists={
        "python": PythonSecurityAgent(),  # Uses bandit patterns
        "javascript": JsSecurityAgent(),  # Uses eslint-security patterns
    },
    generalist=GeneralSecurityAgent(),
)
```

---

## 5. Agent Hooks & Middleware

### 5.1 Hook System

```python
# agents/hooks.py
from typing import Callable, Awaitable
from enum import Enum

class HookPoint(Enum):
    BEFORE_AGENT = "before_agent"
    AFTER_AGENT = "after_agent"
    ON_ERROR = "on_error"

HookFn = Callable[[str, "FileChange", dict], Awaitable[None]]

class HookRegistry:
    """Registry for agent lifecycle hooks."""

    def __init__(self):
        self._hooks: dict[HookPoint, list[HookFn]] = {
            p: [] for p in HookPoint
        }

    def register(self, point: HookPoint, fn: HookFn) -> None:
        self._hooks[point].append(fn)

    async def trigger(
        self,
        point: HookPoint,
        agent_name: str,
        file: "FileChange",
        context: dict,
    ) -> None:
        for hook in self._hooks[point]:
            try:
                await hook(agent_name, file, context)
            except Exception as e:
                log.error("hook.error", point=point, error=str(e))

hooks = HookRegistry()

# Usage: Add metrics collection
async def metrics_hook(agent_name: str, file: FileChange, context: dict):
    await metrics.increment(f"agent.{agent_name}.invocations")

hooks.register(HookPoint.BEFORE_AGENT, metrics_hook)
```

### 5.2 Middleware Pattern

```python
# agents/middleware.py
from typing import Callable, Awaitable

AgentFn = Callable[["FileChange", dict], Awaitable[list["ReviewComment"]]]

class AgentMiddleware:
    """Base class for agent middleware."""

    async def __call__(
        self,
        file: "FileChange",
        context: dict,
        next_fn: AgentFn,
    ) -> list["ReviewComment"]:
        return await next_fn(file, context)

class RateLimitMiddleware(AgentMiddleware):
    """Rate limit LLM calls."""

    def __init__(self, calls_per_minute: int = 60):
        self._semaphore = asyncio.Semaphore(calls_per_minute)

    async def __call__(self, file, context, next_fn):
        async with self._semaphore:
            return await next_fn(file, context)

class CacheMiddleware(AgentMiddleware):
    """Cache agent results for identical inputs."""

    def __init__(self, cache: "Cache"):
        self._cache = cache

    async def __call__(self, file, context, next_fn):
        cache_key = self._make_key(file)

        # Try cache first
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        # Run agent
        result = await next_fn(file, context)

        # Cache result
        await self._cache.set(cache_key, result, ttl=3600)
        return result

class RetryMiddleware(AgentMiddleware):
    """Retry on transient failures."""

    def __init__(self, max_retries: int = 3):
        self._max_retries = max_retries

    async def __call__(self, file, context, next_fn):
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return await next_fn(file, context)
            except TransientError as e:
                last_error = e
                await asyncio.sleep(2 ** attempt)
        raise last_error

# Apply middleware chain
def with_middleware(
    agent_fn: AgentFn,
    middlewares: list[AgentMiddleware],
) -> AgentFn:
    """Wrap agent function with middleware chain."""

    async def wrapped(file: FileChange, context: dict) -> list[ReviewComment]:
        async def run_chain(idx: int) -> list[ReviewComment]:
            if idx >= len(middlewares):
                return await agent_fn(file, context)
            return await middlewares[idx](file, context, lambda f, c: run_chain(idx + 1))

        return await run_chain(0)

    return wrapped
```

---

## 6. Configuration-Driven Agents

### 6.1 Agent Configuration Schema

```yaml
# .reviewer.yaml
agents:
  security:
    enabled: true
    priority: 10
    options:
      check_sql_injection: true
      check_xss: true
      severity_threshold: warning

  style:
    enabled: true
    priority: 50
    options:
      max_line_length: 100
      enforce_docstrings: true

  logic:
    enabled: true
    priority: 30

  # Custom agent from config
  custom_lint:
    enabled: true
    type: "linter"
    command: "npm run lint"
    parser: "eslint"

  # Disable for specific paths
  test_quality:
    enabled: true
    exclude_paths:
      - "vendor/**"
      - "node_modules/**"

# Per-path overrides
path_rules:
  "src/security/**":
    agents:
      security:
        priority: 1 # Run first for security code
        options:
          severity_threshold: info # More strict

  "tests/**":
    agents:
      test_quality:
        enabled: true
      style:
        enabled: false # Less strict for tests
```

### 6.2 Config-Driven Agent Loading

```python
# agents/loader.py
from .registry import registry
from .base import BaseReviewAgent, AgentMetadata, AgentCapability

def load_agents_from_config(config: dict) -> None:
    """Load and configure agents from repository config."""

    agents_config = config.get("agents", {})

    for agent_name, agent_config in agents_config.items():
        agent = registry.get_agent(agent_name)

        if agent:
            # Update existing agent config
            if "enabled" in agent_config:
                agent.metadata.enabled = agent_config["enabled"]
            if "priority" in agent_config:
                agent.metadata.priority = agent_config["priority"]
            if "options" in agent_config:
                agent.set_options(agent_config["options"])

        elif agent_config.get("type") == "linter":
            # Create dynamic linter agent
            agent = create_linter_agent(agent_name, agent_config)
            registry.register(agent)

def create_linter_agent(name: str, config: dict) -> BaseReviewAgent:
    """Create a dynamic agent that runs an external linter."""

    class DynamicLinterAgent(BaseReviewAgent):
        @property
        def metadata(self) -> AgentMetadata:
            return AgentMetadata(
                name=name,
                description=f"Linter: {config.get('command', 'N/A')}",
                version="1.0.0",
                capability=AgentCapability(
                    languages=config.get("languages", ["*"]),
                ),
                priority=config.get("priority", 100),
            )

        async def analyze(self, file, context) -> list[ReviewComment]:
            command = config["command"]
            parser = config.get("parser", "generic")

            # Run external command
            result = await run_command(command, file.filename)

            # Parse output
            return parse_linter_output(result, parser, file)

    return DynamicLinterAgent()
```

---

## 7. Agent Testing Framework

### 7.1 Test Fixtures

```python
# tests/agents/conftest.py
import pytest
from src.agents.state import FileChange

@pytest.fixture
def python_file():
    return FileChange(
        filename="test.py",
        status="modified",
        additions=10,
        deletions=5,
        patch="""
@@ -1,5 +1,10 @@
 def hello():
-    print("world")
+    password = "secret123"  # Security issue
+    query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection
+    return password
""",
        language="python",
    )

@pytest.fixture
def javascript_file():
    return FileChange(
        filename="app.js",
        status="added",
        additions=20,
        deletions=0,
        patch="""...""",
        language="javascript",
    )

@pytest.fixture
def test_file():
    return FileChange(
        filename="test_something.py",
        status="modified",
        additions=15,
        deletions=2,
        patch="""...""",
        language="python",
    )
```

### 7.2 Agent Unit Tests

```python
# tests/agents/test_security_agent.py
import pytest
from src.agents.security_agent import SecurityAgent

class TestSecurityAgent:

    @pytest.fixture
    def agent(self):
        return SecurityAgent()

    def test_should_run_for_python(self, agent, python_file):
        assert agent.should_run(python_file) is True

    def test_should_not_run_for_markdown(self, agent):
        md_file = FileChange(filename="README.md", language="markdown", ...)
        assert agent.should_run(md_file) is False

    @pytest.mark.asyncio
    async def test_detects_hardcoded_password(self, agent, python_file):
        comments = await agent.analyze(python_file, {})

        assert any(
            "password" in c.message.lower() and c.severity in ("critical", "warning")
            for c in comments
        )

    @pytest.mark.asyncio
    async def test_detects_sql_injection(self, agent, python_file):
        comments = await agent.analyze(python_file, {})

        assert any(
            "sql" in c.message.lower() and "injection" in c.message.lower()
            for c in comments
        )
```

### 7.3 Integration Tests

```python
# tests/agents/test_registry.py
from src.agents.registry import registry

def test_registry_returns_correct_agents_for_python():
    python_file = FileChange(filename="app.py", language="python", ...)

    agents = registry.get_agents_for_file(python_file)
    agent_names = [a.metadata.name for a in agents]

    assert "security" in agent_names
    assert "style" in agent_names
    assert "logic" in agent_names

def test_registry_returns_test_agent_for_test_file():
    test_file = FileChange(filename="test_app.py", language="python", ...)

    agents = registry.get_agents_for_file(test_file)
    agent_names = [a.metadata.name for a in agents]

    assert "test_quality" in agent_names

def test_registry_respects_priority_order():
    python_file = FileChange(filename="app.py", language="python", ...)

    agents = registry.get_agents_for_file(python_file)

    # Verify sorted by priority
    priorities = [a.metadata.priority for a in agents]
    assert priorities == sorted(priorities)
```

---

## 8. Adding New Agents Guide

### 8.1 Step-by-Step Guide

1. **Create Agent File**

```python
# src/agents/nodes/my_new_agent.py
from ..base import BaseReviewAgent, AgentMetadata, AgentCapability
from ..registry import registry

@registry.register_class
class MyNewAgent(BaseReviewAgent):
    """Description of what this agent does."""

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="my_new_agent",
            description="Analyzes X for Y issues",
            version="1.0.0",
            capability=AgentCapability(
                languages=["python", "javascript"],
                file_patterns=["*.py", "*.js"],
                categories=["custom"],
            ),
            priority=50,
        )

    async def analyze(
        self,
        file: FileChange,
        context: dict,
    ) -> list[ReviewComment]:
        # Your analysis logic here
        ...
```

2. **Import in `__init__.py`**

```python
# src/agents/nodes/__init__.py
from . import my_new_agent  # Just import to trigger registration
```

3. **Add Tests**

```python
# tests/agents/test_my_new_agent.py
...
```

4. **Update Config Schema** (if needed)

```yaml
# .reviewer.yaml
agents:
  my_new_agent:
    enabled: true
    options:
      custom_option: value
```

### 8.2 Agent Template

```python
"""
Agent: [NAME]
Category: [security|style|logic|testing|custom]
Languages: [python, javascript, ...]
Description: [What does this agent check for?]
"""

from ..base import BaseReviewAgent, AgentMetadata, AgentCapability
from ..registry import registry
from ...core.llm import get_structured_llm
from ...state import FileChange, ReviewComment

# Define structured output for LLM
class MyAgentFindings(BaseModel):
    findings: list[Finding]

class Finding(BaseModel):
    line: int
    severity: Literal["critical", "warning", "info", "suggestion"]
    message: str
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

# System prompt for the agent
PROMPT_TEMPLATE = """
You are a code review agent specialized in [SPECIALIZATION].

## File: {filename}
## Language: {language}

## Code Diff:
```

{diff}

```

Analyze this code and identify [WHAT TO FIND].

Focus on:
1. [Focus area 1]
2. [Focus area 2]
3. [Focus area 3]

Return your findings as JSON.
"""

@registry.register_class
class MyNewAgent(BaseReviewAgent):

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            name="[agent_name]",
            description="[description]",
            version="1.0.0",
            capability=AgentCapability(
                languages=["python"],
                categories=["[category]"],
            ),
            priority=50,
        )

    async def analyze(
        self,
        file: FileChange,
        context: dict,
    ) -> list[ReviewComment]:
        if not file.patch:
            return []

        prompt = PROMPT_TEMPLATE.format(
            filename=file.filename,
            language=file.language or "text",
            diff=file.patch,
        )

        llm = get_structured_llm(MyAgentFindings)
        result = await llm.ainvoke(prompt)

        return [
            ReviewComment(
                file=file.filename,
                line=f.line,
                severity=f.severity,
                category=self.metadata.name,
                message=f.message,
                suggestion=f.suggestion,
                confidence=f.confidence,
                agent=self.metadata.name,
            )
            for f in result.findings
        ]
```
