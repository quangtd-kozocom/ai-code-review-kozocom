# 🤖 AI Code Reviewer

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered code review system** that automatically reviews GitHub Pull Requests using multiple specialized AI agents powered by LangGraph.

> 🎯 **Goal**: Provide instant, high-quality code reviews by combining insights from Security, Style, and Logic analysis agents.

---

## ✨ Features

| Feature                    | Description                                                         |
| -------------------------- | ------------------------------------------------------------------- |
| 🔐 **Multi-Agent Review**  | 3 specialized AI agents: Security, Style, and Logic analysis        |
| 🔗 **GitHub Integration**  | Seamless integration via GitHub Apps with HMAC webhook validation   |
| ⚡ **Async Processing**    | Background processing with Celery + Redis for scalability           |
| 🧠 **Smart Aggregation**   | Deduplication, severity prioritization, and per-file comment limits |
| 🔔 **Slack Notifications** | Optional notifications for completed reviews                        |
| 📊 **Observability**       | Structured logging with Sentry integration                          |

---

## 🏗️ Architecture

```
                           ┌──────────────────────────────────────────────┐
                           │              GITHUB PR EVENT                 │
                           └──────────────────────┬───────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI (Webhook Handler)                               │
│  • HMAC-SHA256 signature verification                                                │
│  • Event filtering (opened, synchronize, reopened)                                   │
│  • Queue task to Celery                                                              │
└─────────────────────────────────────────────────┬───────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CELERY WORKER (Background)                              │
│                                                                                      │
│  ┌──────────────┐                                                                    │
│  │   Extract    │ ← Fetch PR files from GitHub API                                   │
│  └──────┬───────┘                                                                    │
│         │                                                                            │
│         ├──────────────────┬──────────────────┐                                      │
│         ▼                  ▼                  ▼                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                               │
│  │  Security   │    │    Style    │    │    Logic    │  ← Run in parallel            │
│  │    Agent    │    │    Agent    │    │    Agent    │                               │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                               │
│         │                  │                  │                                      │
│         └──────────────────┼──────────────────┘                                      │
│                            ▼                                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐            │
│  │                        Aggregator                                     │            │
│  │  • Deduplicate similar comments                                       │            │
│  │  • Sort by severity (critical > warning > info > suggestion)         │            │
│  │  • Limit comments per file                                           │            │
│  └──────────────────────────────────┬───────────────────────────────────┘            │
│                                     ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐            │
│  │                      GitHub Publisher                                 │            │
│  │  • Format comments with severity badges                              │            │
│  │  • Post review via GitHub API                                        │            │
│  └──────────────────────────────────┬───────────────────────────────────┘            │
│                                     ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐            │
│  │                      Slack Reporter (Optional)                        │            │
│  │  • Send notification about review                                    │            │
│  └──────────────────────────────────────────────────────────────────────┘            │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 AI Agents

Each agent specializes in a specific aspect of code review:

| Agent                 | Focus Areas                                                            |
| --------------------- | ---------------------------------------------------------------------- |
| 🔒 **Security Agent** | SQL injection, XSS, SSRF, hardcoded secrets, insecure configurations   |
| 🎨 **Style Agent**    | Naming conventions, code formatting, dead code, missing documentation  |
| 🧠 **Logic Agent**    | Null references, off-by-one errors, missing error handling, edge cases |

All agents use an LLM (OpenAI GPT-4 or Anthropic Claude) to analyze code diffs and provide actionable feedback with confidence scores.

---

## 📁 Project Structure

```
src/
├── app/                    # FastAPI Application Layer
│   ├── api/v1/             # API endpoints
│   │   ├── webhooks.py     # GitHub webhook handler
│   │   └── router.py       # Route definitions
│   ├── services/           # External integrations
│   │   ├── github.py       # GitHub API client
│   │   └── slack.py        # Slack notifications
│   ├── config.py           # Pydantic Settings
│   └── main.py             # App entrypoint
├── agents/                 # LangGraph AI Layer
│   ├── nodes/              # Agent implementations
│   │   ├── security_agent.py
│   │   ├── style_agent.py
│   │   ├── logic_agent.py
│   │   ├── context_extractor.py
│   │   ├── aggregator.py
│   │   ├── github_publisher.py
│   │   └── slack_reporter.py
│   ├── prompts/            # LLM prompts
│   ├── graph.py            # LangGraph workflow
│   └── state.py            # GraphState schema
├── core/                   # Shared Utilities
│   ├── llm.py              # LLM client factory
│   └── logging.py          # Structured logging
└── workers/                # Celery Background Tasks
    ├── celery_app.py       # Celery configuration
    └── tasks.py            # Task definitions
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **[uv](https://github.com/astral-sh/uv)** (recommended) or pip
- **Redis** (local) or [Upstash](https://upstash.com/) (cloud)
- **GitHub App** credentials ([create one here](https://github.com/settings/apps))
- **OpenAI** or **Anthropic** API key

### 🔧 Step 1: Create a GitHub App

1. Go to [GitHub Settings > Developer settings > GitHub Apps](https://github.com/settings/apps)

2. Click **"New GitHub App"**

3. Fill in the basic information:
   | Field | Value |
   |-------|-------|
   | **GitHub App name** | `AI Code Reviewer` (or your preferred name) |
   | **Homepage URL** | Your website or repo URL |
   | **Webhook URL** | `https://your-domain.com/api/v1/webhooks/github` (update later with ngrok) |
   | **Webhook secret** | Generate a secure random string |

4. Set **Permissions**:

   **Repository permissions:**
   | Permission | Access |
   |------------|--------|
   | Contents | Read |
   | Metadata | Read |
   | Pull requests | Read & Write |

   **Subscribe to events:**

   - ✅ Pull request

5. Click **"Create GitHub App"**

6. After creation, note down:
   - **App ID** (shown at the top)
   - **Generate a private key** (download the `.pem` file)

### 🔧 Step 2: Install the App on Your Repository

1. Go to your GitHub App settings page

2. Click **"Install App"** in the left sidebar

3. Choose the account/organization

4. Select repositories:

   - **All repositories** - App will review all repos
   - **Only select repositories** - Choose specific repos to review

5. Click **"Install"**

6. Note down the **Installation ID** from the URL:
   ```
   https://github.com/settings/installations/INSTALLATION_ID
   ```

### 🔧 Step 3: Configure Environment Variables

Create `.env` file with your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# GitHub App (from Step 1)
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...your private key content...
-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# LLM (at least one required)
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...

# Redis
REDIS_URL=redis://localhost:6379
# or Upstash: rediss://default:xxx@xxx.upstash.io:6379

# Optional
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#pr-reviews
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
```

> ⚠️ **Note**: For the private key, you can either paste the content directly (with `\n` for newlines) or use a file path.

### 🔧 Step 4: Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ai-code-reviewer.git
cd ai-code-reviewer

# Install dependencies
uv sync

# Or using pip
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration section)
```

### 🔧 Step 5: Run Locally

```bash
# Terminal 1: Start the FastAPI server
make dev

# Terminal 2: Start the Celery worker
make worker
```

The API will be available at `http://localhost:8000`.

### 🔧 Step 6: Quick Start Scripts (Recommended)

Use the convenient startup scripts for a better developer experience:

```bash
# Start API + Worker (all-in-one)
./scripts/start.sh

# Start with ngrok tunnel for public access
./scripts/start.sh --ngrok

# Start in tmux with API+Worker and ngrok in separate panes (best for development)
./scripts/start.sh --tmux

# Start API only with hot-reload (dev mode)
./scripts/start.sh --dev

# Stop all services
./scripts/stop.sh
```

#### Script Options

| Option    | Description                                                  |
| --------- | ------------------------------------------------------------ |
| `--ngrok` | Start ngrok tunnel to expose local server to the internet    |
| `--tmux`  | Start in tmux session with split panes (API+Worker \| ngrok) |
| `--dev`   | Development mode - API only with auto-reload                 |
| `--help`  | Show help message                                            |

#### tmux Mode Features

When using `--tmux`, you get:

- **Split panes**: Left pane for API+Worker, Right pane for ngrok
- **Auto-configured**: ngrok starts with your configured domain
- **Easy navigation**: Use `Ctrl+B, ←/→` to switch between panes
- **Detach/Attach**: Use `Ctrl+B, D` to detach, `tmux attach -t ai-reviewer` to reattach

### 🔧 Step 7: Expose to Internet (ngrok)

```bash
# Expose local server to the internet
ngrok http 8000

# Or use the start script with ngrok
./scripts/start.sh --ngrok
```

### 🔧 Step 8: Update GitHub App Webhook URL

1. Go to your [GitHub App settings](https://github.com/settings/apps)
2. Click on your app name
3. Update **Webhook URL** to your ngrok URL:
   ```
   https://your-ngrok-id.ngrok.io/api/v1/webhooks/github
   ```
4. Click **Save changes**

> 💡 **Tip**: Use a static ngrok domain (paid feature) or update the URL each time you restart ngrok.

### ✅ Step 9: Test the Setup

1. Create or update a Pull Request on your installed repository
2. Watch the terminal logs for incoming webhook
3. AI agents will analyze the code and post comments on the PR

```bash
# Expected log output
[INFO] Received webhook: pull_request.opened
[INFO] Queued review task for PR #123
[INFO] Running security agent...
[INFO] Running style agent...
[INFO] Running logic agent...
[INFO] Posted review to GitHub
```

---

## ⚙️ Configuration

Configure via environment variables or `.env` file:

| Variable                | Required | Description                                   |
| ----------------------- | -------- | --------------------------------------------- |
| `GITHUB_APP_ID`         | ✅       | GitHub App ID                                 |
| `GITHUB_PRIVATE_KEY`    | ✅       | GitHub App private key (PEM format)           |
| `GITHUB_WEBHOOK_SECRET` | ✅       | Secret for webhook signature verification     |
| `OPENAI_API_KEY`        | ⚡       | OpenAI API key (at least one LLM required)    |
| `ANTHROPIC_API_KEY`     | ⚡       | Anthropic API key (at least one LLM required) |
| `REDIS_URL`             | ✅       | Redis connection URL                          |
| `SLACK_BOT_TOKEN`       | ❌       | Slack bot token (optional)                    |
| `SLACK_CHANNEL`         | ❌       | Slack channel for notifications               |
| `SENTRY_DSN`            | ❌       | Sentry DSN for error tracking                 |
| `DEBUG`                 | ❌       | Enable debug mode (default: false)            |
| `LOG_LEVEL`             | ❌       | Logging level (default: INFO)                 |

---

## 📋 Available Commands

```bash
make install    # Install dependencies
make dev        # Run FastAPI in development mode (with reload)
make run        # Run FastAPI in production mode
make worker     # Start Celery worker
make test       # Run tests
make lint       # Check code style with Ruff
make format     # Auto-format code with Ruff
make clean      # Remove __pycache__ directories
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_webhooks.py -v
```

---

## 🔐 Security

### GitHub App Authentication

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Private   │   JWT   │   GitHub    │  Token  │   GitHub    │
│     Key     │ ──────▶ │    API      │ ──────▶ │    API      │
│  (RS256)    │         │  /access_   │         │  /repos/... │
└─────────────┘         │   tokens    │         └─────────────┘
                        └─────────────┘

JWT lifetime: 10 minutes
Installation Token lifetime: 1 hour
```

### Webhook Signature Verification

All incoming webhooks are verified using HMAC-SHA256:

```python
expected = hmac.new(WEBHOOK_SECRET, body, sha256).hexdigest()
hmac.compare_digest(f"sha256={expected}", signature)  # Timing-safe
```

---

## 📊 Sample Review Output

When a PR is reviewed, comments appear directly on GitHub:

> 🔴 **CRITICAL** (security)
>
> SQL injection vulnerability via f-string interpolation
>
> **Suggestion:** Use parameterized queries instead:
>
> ```python
> cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
> ```

---

## 📈 Scalability

| Aspect                  | Strategy                                   |
| ----------------------- | ------------------------------------------ |
| **Horizontal Scaling**  | Add more Celery workers                    |
| **Rate Limiting**       | GitHub API: 5000 req/hour per installation |
| **Token Caching**       | Installation tokens cached for ~1 hour     |
| **Parallel Processing** | 3 agents run concurrently via LangGraph    |

---

## 📚 Documentation

- [How It Works](./docs/explain/HOW_IT_WORKS.md) - Detailed system architecture
- [Phase 1: MVP](./docs/phases/PHASE_1_MVP.md) - Initial implementation
- [Phase 2: Enhanced](./docs/phases/PHASE_2_ENHANCED.md) - Advanced features
- [Phase 3: Scale](./docs/phases/PHASE_3_SCALE.md) - Production scaling
- [AI Agent Guidelines](./AGENTS.md) - Guidelines for AI code generation

---

## 🛠️ Tech Stack

| Category             | Technologies                            |
| -------------------- | --------------------------------------- |
| **Web Framework**    | FastAPI, Uvicorn, Pydantic              |
| **AI/ML**            | LangGraph, LangChain, OpenAI, Anthropic |
| **Background Tasks** | Celery, Redis                           |
| **HTTP Client**      | httpx                                   |
| **Authentication**   | PyJWT, Cryptography                     |
| **Observability**    | structlog, Sentry                       |
| **Notifications**    | Slack SDK                               |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`make test && make lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ by the AI Code Reviewer Team
</p>
