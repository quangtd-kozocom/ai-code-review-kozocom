# 🤖 AI Code Reviewer

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered code review system** that automatically detects breaking changes in GitHub Pull Requests using LangGraph-based workflow.

> 🎯 **Goal**: Detect breaking changes that could affect other parts of the codebase and provide actionable recommendations.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Breaking Change Detection** | Automatically detects signature changes, deletions, visibility changes that could break callers |
| 🔗 **GitHub Integration** | Seamless integration via GitHub Apps with HMAC webhook validation |
| ⚡ **Async Processing** | Background processing with Celery + Redis for scalability |
| 🗄️ **Database Storage** | PostgreSQL storage for reviews, breaking changes, and affected callers |
| 🌐 **Multi-language Output** | Support for English, Vietnamese, Japanese, Chinese review output |
| ⚙️ **Per-repo Configuration** | Configurable include/exclude patterns, auto-review, output language per repository |
| 💬 **Chat Commands** | Interactive commands: `@reviewer explain`, `@reviewer fix`, `@reviewer tests` |
| 📊 **Observability** | Structured logging with Sentry integration |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           GITHUB PR EVENT                                     │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI (Webhook Handler)                              │
│  • HMAC-SHA256 signature verification                                         │
│  • Event filtering (opened, synchronize, reopened)                            │
│  • Queue task to Celery                                                       │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        CELERY WORKER (Background)                             │
│                                                                               │
│  ┌─────────────────┐                                                          │
│  │  Load Config    │ ← Get repo config from Redis cache / DB                  │
│  └────────┬────────┘                                                          │
│           │                                                                   │
│  ┌────────▼────────┐                                                          │
│  │  Extract Diff   │ ← Fetch PR files, filter by include/exclude patterns     │
│  └────────┬────────┘                                                          │
│           │                                                                   │
│  ┌────────▼────────┐                                                          │
│  │  Clone Repo     │ ← Shallow clone for ripgrep search                       │
│  └────────┬────────┘                                                          │
│           │                                                                   │
│           ▼ (for each modified file)                                          │
│  ┌──────────────────────────────────────────────────────────────────┐         │
│  │                    FILE PROCESSING LOOP                           │         │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │         │
│  │  │ Analyze     │→ │ Plan Search │→ │ Execute     │               │         │
│  │  │ File (LLM)  │  │ (LLM)       │  │ Search (rg) │               │         │
│  │  └─────────────┘  └─────────────┘  └──────┬──────┘               │         │
│  │                                           │                       │         │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────▼──────┐               │         │
│  │  │ Generate    │← │ Verify      │← │ Search      │               │         │
│  │  │ Review      │  │ Impact(LLM) │  │ Results     │               │         │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │         │
│  └──────────────────────────────────────────────────────────────────┘         │
│           │                                                                   │
│  ┌────────▼────────┐                                                          │
│  │ Publish GitHub  │ ← Post inline/issue comments (if enabled)                │
│  └────────┬────────┘                                                          │
│           │                                                                   │
│  ┌────────▼────────┐                                                          │
│  │ Finalize Review │ ← Save to DB, notify Slack                               │
│  └─────────────────┘                                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Breaking Change Detection

The system detects changes that could break existing callers:

| Change Type | Description |
|-------------|-------------|
| **Signature Changes** | Added required parameters, removed parameters, type changes |
| **Deletions** | Removed functions, constants, classes, methods |
| **Visibility Changes** | Public → private/protected |
| **Contract Changes** | Added required methods to interfaces |
| **Renames** | Renamed without aliases |

### How It Works

1. **Analyze File** - LLM analyzes diff to detect potential breaking changes
2. **Plan Search** - LLM generates search queries to find callers
3. **Execute Search** - ripgrep searches the codebase for usages
4. **Verify Impact** - LLM confirms which callers will actually break
5. **Generate Review** - Creates actionable review comments

---

## 📁 Project Structure

```
src/
├── app/                      # FastAPI Application Layer
│   ├── api/v1/               # API endpoints
│   │   ├── webhooks.py       # GitHub webhook handler
│   │   ├── reviews.py        # Review API endpoints
│   │   ├── repositories.py   # Repository & config API
│   │   └── router.py         # Route definitions
│   ├── services/             # External integrations
│   │   ├── github/           # GitHub API client (modular)
│   │   │   ├── client.py     # Base client with auth
│   │   │   ├── pr.py         # PR operations
│   │   │   ├── files.py      # File content operations
│   │   │   ├── comments.py   # Comment operations
│   │   │   └── search.py     # Code search
│   │   └── slack.py          # Slack notifications
│   ├── config.py             # Pydantic Settings
│   └── main.py               # App entrypoint
├── agents/                   # LangGraph AI Layer
│   ├── nodes/                # Workflow nodes
│   │   ├── extract_diff.py   # Fetch PR files from GitHub
│   │   ├── clone_repo.py     # Shallow clone for search
│   │   ├── get_next_file.py  # File loop management
│   │   ├── analyze_file.py   # LLM detects breaking changes
│   │   ├── plan_search.py    # LLM generates search queries
│   │   ├── execute_search.py # Run ripgrep searches
│   │   ├── verify_impact.py  # LLM confirms affected callers
│   │   ├── generate_file_review.py # Create review comments
│   │   ├── publish_github.py # Post to GitHub
│   │   └── finalize_review.py # Save to DB, notify Slack
│   ├── prompts/              # LLM prompts (multi-language)
│   ├── locales.py            # i18n strings (en, vi, ja, zh)
│   ├── constants.py          # Node names, thresholds
│   ├── models.py             # Pydantic models for LLM output
│   ├── graph.py              # LangGraph workflow definition
│   └── state.py              # Workflow state schema
├── analysis/                 # Code Analysis
│   ├── diff_extractor.py     # Parse GitHub diffs
│   ├── ast_analyzer.py       # Tree-sitter AST parsing
│   └── models.py             # Analysis data models
├── chat/                     # Chat Commands (@reviewer)
│   ├── handlers/             # Command handlers
│   │   ├── base.py           # Base handler class
│   │   ├── explain.py        # @reviewer explain
│   │   ├── fix.py            # @reviewer fix
│   │   └── generate_tests.py # @reviewer tests
│   ├── commands.py           # CommandType enum
│   ├── context.py            # CommandContext dataclass
│   ├── parser.py             # Parse @reviewer commands
│   └── handler.py            # Command dispatcher
├── core/                     # Shared Utilities
│   ├── models/               # SQLModel database models
│   │   ├── repository.py     # Repository model
│   │   ├── repo_config.py    # Per-repo configuration
│   │   ├── pr_review.py      # PR review record
│   │   ├── breaking_change.py # Breaking change record
│   │   ├── affected_caller.py # Affected caller record
│   │   └── review_comment.py # Review comment record
│   ├── repositories/         # Data access layer
│   │   └── review_repository.py
│   ├── services/             # Business services
│   │   └── config_service.py # Config with Redis cache
│   ├── constants.py          # Shared constants
│   ├── database.py           # PostgreSQL connection
│   ├── redis.py              # Redis connection
│   ├── llm.py                # LLM client factory
│   ├── logging.py            # structlog setup
│   └── i18n.py               # Internationalization
└── workers/                  # Celery Background Tasks
    ├── celery_app.py         # Celery configuration
    └── tasks.py              # Task definitions
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.14+** (required - uses latest Python features)
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[ripgrep](https://github.com/BurntSushi/ripgrep)** - Required for breaking change detection
- **Redis** - For Celery task queue and caching
- **PostgreSQL** - For storing reviews (optional but recommended)
- **GitHub App** - For webhook integration
- **LLM API Key** - OpenRouter, OpenAI, Anthropic, or Google

### Step 1: Install System Dependencies

```bash
# macOS
brew install python@3.14 ripgrep redis

# Ubuntu/Debian
sudo apt update
sudo apt install ripgrep redis-server
# Python 3.14 - install from source or use pyenv

# Windows
choco install ripgrep redis-64
# Python 3.14 - download from python.org
```

### Step 2: Install uv (Python Package Manager)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 3: Clone and Setup Project

```bash
# Clone the repository
git clone https://github.com/your-org/ai-code-reviewer.git
cd ai-code-reviewer

# Install dependencies (creates .venv automatically)
uv sync

# Copy environment template
cp .env.example .env
```

### Step 4: Configure Environment Variables

Edit `.env` with your credentials:

```bash
# ======================
# Required Configuration
# ======================

# GitHub App (create at https://github.com/settings/apps)
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# Redis (local or cloud like Upstash)
REDIS_URL=redis://localhost:6379
# For Upstash: rediss://default:xxx@xxx.upstash.io:6379

# LLM Provider (at least one required)
# Priority: Google → OpenRouter → OpenAI → Anthropic

# Option 1: Google AI (recommended - has free tier)
GOOGLE_API_KEY=AIza...
GOOGLE_DEFAULT_MODEL=gemini-2.0-flash

# Option 2: OpenRouter (200+ models)
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3.5-sonnet

# Option 3: Direct providers
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# ======================
# Optional Configuration
# ======================

# PostgreSQL (for storing reviews)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reviewer

# Slack notifications
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#pr-reviews

# Sentry error tracking
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx

# App settings
DEBUG=false
LOG_LEVEL=INFO
```

### Step 5: Create GitHub App

1. Go to [GitHub Settings > Developer settings > GitHub Apps](https://github.com/settings/apps)
2. Click "New GitHub App"
3. Configure:
   - **Name**: AI Code Reviewer (or your choice)
   - **Homepage URL**: Your app URL
   - **Webhook URL**: `https://your-domain.com/api/v1/webhooks/github`
   - **Webhook secret**: Generate a secure secret
   - **Permissions**:
     - Repository permissions:
       - Contents: Read
       - Pull requests: Read & Write
       - Issues: Read & Write
     - Subscribe to events:
       - Pull request
       - Issue comment
       - Pull request review comment
4. Generate and download private key
5. Install the app on your repositories

### Step 6: Start Services

```bash
# Option 1: Start all services (API + Worker)
./scripts/start.sh

# Option 2: Start with ngrok tunnel (for public webhook)
./scripts/start.sh --ngrok

# Option 3: Start in tmux (split panes)
./scripts/start.sh --tmux

# Option 4: Development mode (API only with hot-reload)
./scripts/start.sh --dev
```

Or start manually:

```bash
# Terminal 1: Start FastAPI server
make dev

# Terminal 2: Start Celery worker
make worker
```

### Step 7: Verify Installation

```bash
# Check health endpoint
curl http://localhost:9000/health
# Expected: {"status":"ok"}

# Check API docs
open http://localhost:9000/docs
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_APP_ID` | ✅ | - | GitHub App ID |
| `GITHUB_PRIVATE_KEY` | ✅ | - | GitHub App private key (PEM format) |
| `GITHUB_WEBHOOK_SECRET` | ✅ | - | Secret for webhook signature verification |
| `REDIS_URL` | ✅ | - | Redis connection URL |
| `DATABASE_URL` | ❌ | - | PostgreSQL connection URL |
| `GOOGLE_API_KEY` | ⚡ | - | Google AI API key |
| `OPENROUTER_API_KEY` | ⚡ | - | OpenRouter API key |
| `OPENAI_API_KEY` | ⚡ | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | ⚡ | - | Anthropic API key |
| `SLACK_BOT_TOKEN` | ❌ | - | Slack bot token |
| `SLACK_CHANNEL` | ❌ | `#pr-reviews` | Slack channel for notifications |
| `SENTRY_DSN` | ❌ | - | Sentry DSN for error tracking |
| `DEBUG` | ❌ | `false` | Enable debug mode |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |

⚡ At least one LLM API key is required

### Per-Repository Configuration

Each repository can have its own configuration stored in the database:

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable reviews for this repo |
| `auto_review` | `true` | Automatically review new PRs |
| `review_on_update` | `false` | Re-review on PR updates |
| `include_patterns` | `[]` | File patterns to include (empty = all) |
| `exclude_patterns` | `[*.min.js, *.lock, ...]` | File patterns to exclude |
| `output_language` | `en` | Output language: `en`, `vi`, `ja`, `zh` |
| `github_comment` | `true` | Post comments to GitHub |
| `slack_channel` | `null` | Override Slack channel |
| `slack_notify_on` | `critical` | When to notify: `all`, `critical`, `none` |

---

## 💬 Chat Commands

Interact with the reviewer by commenting on PRs:

| Command | Description |
|---------|-------------|
| `@reviewer explain` | Explain the breaking change in detail |
| `@reviewer fix` | Suggest code fix for the issue |
| `@reviewer tests` | Generate test cases for the change |
| `@reviewer help` | Show available commands |

### Examples

```
@reviewer explain
# Explains why the detected change is problematic

@reviewer fix
# Suggests a code fix for the breaking change

@reviewer tests
# Generates unit tests for the changed code
```

---

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/webhooks/github` | POST | GitHub webhook handler |
| `/api/v1/reviews` | GET | List all reviews |
| `/api/v1/reviews/{id}` | GET | Get review details with breaking changes |
| `/api/v1/repositories` | GET | List repositories |
| `/api/v1/repositories/{id}/config` | GET | Get repository config |
| `/api/v1/repositories/{id}/config` | PUT | Update repository config |

---

## 📋 Available Commands

```bash
# Development
make install    # Install dependencies (uv sync)
make dev        # Run FastAPI in development mode (port 9000, hot-reload)
make run        # Run FastAPI in production mode
make worker     # Start Celery worker

# Testing
make test       # Run all tests
uv run pytest tests/unit -v  # Run unit tests only

# Code Quality
make lint       # Check code style with Ruff
make format     # Auto-format code with Ruff
make clean      # Remove __pycache__ and *.pyc

# Scripts
./scripts/start.sh          # Start API + Worker
./scripts/start.sh --ngrok  # With ngrok tunnel
./scripts/start.sh --tmux   # In tmux split panes
./scripts/start.sh --dev    # Dev mode only
./scripts/stop.sh           # Stop all services
```

---

## 🛠️ Tech Stack

| Category | Technologies |
|----------|--------------|
| **Language** | Python 3.14+ |
| **Web Framework** | FastAPI, Uvicorn, Pydantic |
| **AI/ML** | LangGraph, LangChain, OpenAI, Anthropic, Google AI |
| **Database** | PostgreSQL, SQLModel (async) |
| **Cache/Queue** | Redis, Celery |
| **Code Search** | ripgrep |
| **AST Parsing** | tree-sitter |
| **HTTP Client** | httpx (async) |
| **Observability** | structlog, Sentry |
| **Package Manager** | uv |

---

## 🔧 Development

### Code Style

- **Python 3.14** - Uses latest features (type param syntax, improved generics)
- **Ruff** - Linting and formatting (line-length=100)
- **Type hints** - Required everywhere
- **async/await** - For all I/O operations
- **structlog** - For structured logging

### Adding a New LangGraph Node

1. Create node in `src/agents/nodes/new_node.py`:

```python
import structlog
from ..state import ReviewState

log = structlog.get_logger()

async def run(state: ReviewState) -> dict:
    """Node description."""
    log.info("new_node.started")
    # Your logic here
    return {"some_state_key": result}
```

2. Register in `src/agents/graph.py`:

```python
from .nodes import new_node

graph.add_node("new_node", new_node.run)
graph.add_edge("previous_node", "new_node")
```

### Adding a New Chat Command

1. Add to `src/chat/commands.py`:

```python
class CommandType(StrEnum):
    NEW_CMD = "newcmd"
```

2. Create handler in `src/chat/handlers/new_cmd.py`:

```python
from .base import BaseCommandHandler

class NewCmdHandler(BaseCommandHandler):
    async def execute(self, ctx: CommandContext) -> str:
        # Your logic
        return "Response"
```

3. Register in `src/chat/handler.py`:

```python
_handlers = {
    CommandType.NEW_CMD: NewCmdHandler,
}
```

---

## 🐛 Troubleshooting

### Common Issues

**ripgrep not found**
```bash
# macOS
brew install ripgrep

# Ubuntu
apt install ripgrep
```

**Redis connection refused**
```bash
# Start Redis
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis
```

**GitHub webhook not receiving events**
- Check webhook URL is publicly accessible
- Verify webhook secret matches
- Check GitHub App permissions
- Use ngrok for local development: `./scripts/start.sh --ngrok`

**LLM API errors**
- Verify API key is correct
- Check rate limits
- Try a different provider

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
