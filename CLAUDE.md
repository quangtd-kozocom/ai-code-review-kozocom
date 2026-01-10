# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered code review system that automatically reviews GitHub Pull Requests using multiple specialized AI agents powered by LangGraph. When a PR is opened/updated, a webhook triggers Celery workers to run Security, Style, and Logic agents in parallel, then aggregate and post review comments to GitHub.

## Common Commands

```bash
# Development
make install    # Install dependencies (uv sync)
make dev        # Run FastAPI with hot-reload (port 8000)
make worker     # Start Celery worker

# Testing
make test                           # Run all tests
uv run pytest tests/test_file.py -v # Run specific test file
uv run pytest tests/ -k "test_name" # Run test by name

# Code quality
make lint       # Check with Ruff
make format     # Auto-format with Ruff

# Convenience scripts
./scripts/start.sh          # Start API + Worker
./scripts/start.sh --ngrok  # With ngrok tunnel
./scripts/start.sh --tmux   # Split panes (API+Worker | ngrok)
./scripts/stop.sh           # Stop all services
```

## Architecture

### Core Flow

```
GitHub PR Webhook → FastAPI → Celery Task → LangGraph Workflow → GitHub Comments
```

### LangGraph Workflow (`src/agents/graph.py`)

The review workflow processes PRs through these nodes:
1. **acknowledger** - Posts initial "review started" comment to PR
2. **context_extractor** - Fetches PR files from GitHub API
3. **smart_router** - Determines which agents should analyze each file
4. **security/style/logic** (parallel) - Three specialized review agents
5. **aggregator** - Deduplicates and prioritizes comments
6. **github_publisher** - Posts review comments to PR
7. **slack_reporter** - Sends optional Slack notification

State flows through `GraphState` (TypedDict) with comments merged via `operator.add`.

### Module Structure

- **src/app/** - FastAPI layer: webhooks, config, external service clients
- **src/agents/** - LangGraph workflow: nodes, prompts, state, models
- **src/chat/** - On-demand commands (`@reviewer fix/explain/tests`)
- **src/rag/** - RAG system: indexer, embedder, retriever, vector store (Pinecone)
- **src/ast/** - AST parsing with tree-sitter for code structure extraction
- **src/workers/** - Celery tasks for background processing
- **src/core/** - Shared utilities: LLM client, logging, config, constants

### Key Patterns

**Agent nodes** return partial state updates:
```python
async def run(state: GraphState) -> dict:
    llm = get_llm().with_structured_output(AgentFindings)
    # Process files and return comments
    return {"comments": comments}
```

**Chat command handlers** extend `BaseHandler`:
```python
class FixHandler(BaseHandler):
    async def handle(self, ctx: CommandContext) -> str:
        # Use LLM with structured output, return formatted response
```

**LLM calls** use structured output with Pydantic models:
```python
llm = get_llm().with_structured_output(AgentFindings)
result = await llm.ainvoke(prompt)
```

### RAG + AST Integration

`EnhancedFileChange` combines diff content with:
- AST info (functions, classes with signatures/decorators/types)
- Related code from RAG retrieval

This context is formatted via `format_for_prompt()` for richer agent analysis.

## Code Style

- **Python 3.14** - Use latest features to keep code concise (type param syntax `def foo[T]()`, improved generics, etc.)
- Ruff (line-length=100)
- Type hints everywhere
- async/await for I/O
- structlog for logging (not print)
- Keep prompts in `prompts/` directories
- Use `get_settings()` and `get_llm()` factory functions
