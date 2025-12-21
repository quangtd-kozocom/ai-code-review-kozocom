# 📋 Product Requirements Document (PRD)

## AI-Powered Code Review System

**Version:** 1.0  
**Ngày tạo:** 21/12/2024  
**Tác giả:** AI Assistant  
**Trạng thái:** Draft

---

## 📑 Mục lục

1. [Executive Summary](#1-executive-summary)
2. [Đánh giá bản phác thảo](#2-đánh-giá-bản-phác-thảo)
3. [Tổng quan sản phẩm](#3-tổng-quan-sản-phẩm)
4. [Kiến trúc hệ thống](#4-kiến-trúc-hệ-thống)
5. [Tech Stack đề xuất](#5-tech-stack-đề-xuất)
6. [Chi tiết thiết kế LangGraph](#6-chi-tiết-thiết-kế-langgraph)
7. [Tính năng chi tiết](#7-tính-năng-chi-tiết)
8. [API Specifications](#8-api-specifications)
9. [Bảo mật & Compliance](#9-bảo-mật--compliance)
10. [Kế hoạch triển khai](#10-kế-hoạch-triển-khai)
11. [Metrics & KPIs](#11-metrics--kpis)
12. [Rủi ro & Giải pháp](#12-rủi-ro--giải-pháp)

---

## 1. Executive Summary

### 1.1 Mục tiêu

Xây dựng một hệ thống AI Code Review tự động, tương tự CodeRabbit, có khả năng phân tích mã nguồn trong Pull Request và đưa ra các nhận xét có giá trị, giúp giảm thời gian review và nâng cao chất lượng code.

### 1.2 Tầm nhìn

Trở thành công cụ không thể thiếu trong quy trình CI/CD của team, giảm **50%** thời gian code review và phát hiện **80%** các vấn đề tiềm ẩn trước khi merge.

### 1.3 Giá trị mang lại

| Giá trị                 | Mô tả                                       |
| ----------------------- | ------------------------------------------- |
| **Tiết kiệm thời gian** | Tự động hóa các review lặp đi lặp lại       |
| **Nhất quán**           | Đảm bảo tuân thủ coding standards           |
| **Học hỏi**             | Cung cấp feedback có giá trị cho developers |
| **Tích hợp**            | Hoạt động liền mạch trong workflow hiện tại |

---

## 2. Đánh giá bản phác thảo

### 2.1 ✅ Điểm mạnh

| Khía cạnh                      | Đánh giá                                                                                                        |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **Event-Driven Architecture**  | Rất phù hợp cho use case này. Webhook-driven approach đảm bảo real-time response                                |
| **LangGraph Choice**           | Excellent choice! LangGraph là framework tốt nhất hiện tại cho multi-agent orchestration với stateful workflows |
| **Parallel Agents Design**     | Map-Reduce pattern cho phép scale horizontally và giảm latency đáng kể                                          |
| **Review Aggregator**          | Critical node - "Senior LLM" filtering là approach thông minh để giảm false positives                           |
| **Multi-channel Notification** | GitHub + Slack coverage đảm bảo visibility tốt                                                                  |

### 2.2 ⚠️ Điểm cần bổ sung/cải thiện

| Vấn đề                           | Khuyến nghị                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| **Caching Layer**                | Thiếu caching strategy cho diff analysis và similar code patterns                       |
| **Rate Limiting**                | Chưa đề cập đến việc handle GitHub API rate limits (5000 requests/hour)                 |
| **Context Window Management**    | Large PRs có thể exceed LLM context window - cần chunking strategy                      |
| **Incremental Review**           | Nên support review chỉ phần code mới thay vì full PR khi có commits mới                 |
| **Human-in-the-Loop**            | Thiếu mechanism cho developers tương tác với bot (chat, dismiss, request re-review)     |
| **Observability**                | Cần thêm comprehensive logging, tracing, và metrics                                     |
| **Configuration per Repository** | Cần YAML-based config cho mỗi repo (ignore patterns, custom rules, severity thresholds) |

### 2.3 🔧 Đề xuất Node bổ sung

```
New Node: Configuration Loader
├── Load .ai-reviewer.yaml từ repository
├── Parse custom rules và rulesets
└── Override default behaviors

New Node: Context Enricher
├── Fetch related issues/tickets (Jira/Linear integration)
├── Load relevant documentation
└── Historical code review patterns

New Node: Feedback Collector
├── Handle @bot commands trong PR comments
├── Learn từ accepted/rejected suggestions
└── Update internal knowledge base
```

---

## 3. Tổng quan sản phẩm

### 3.1 User Personas

#### Primary: Developer

- **Nhu cầu:** Nhận feedback nhanh, actionable suggestions
- **Pain points:** Review chậm, feedback không nhất quán
- **Goals:** Merge code nhanh hơn với confidence cao hơn

#### Secondary: Tech Lead / Senior Developer

- **Nhu cầu:** Đảm bảo team tuân thủ standards
- **Pain points:** Không đủ bandwidth để review tất cả PRs
- **Goals:** Scale review capacity mà không giảm chất lượng

#### Tertiary: Engineering Manager

- **Nhu cầu:** Visibility vào code quality metrics
- **Pain points:** Khó đo lường và cải thiện code quality
- **Goals:** Data-driven insights về development process

### 3.2 User Stories

```
Epic: Automated Code Review

US-001: Automatic PR Analysis
AS A developer
I WANT my PR to be automatically reviewed when I create it
SO THAT I get immediate feedback without waiting for reviewers

Acceptance Criteria:
- Review starts within 30 seconds of PR creation
- Comments appear within 5 minutes for average PR
- Line-level comments point to exact issues

US-002: Incremental Review
AS A developer
I WANT new commits to be incrementally reviewed
SO THAT I don't re-receive the same feedback

US-003: Customizable Rules
AS A tech lead
I WANT to configure review rules per repository
SO THAT the bot follows our team's coding standards

US-004: Slack Notifications
AS A team member
I WANT to receive PR summaries in Slack
SO THAT I'm aware of code changes without checking GitHub

US-005: Interactive Chat
AS A developer
I WANT to ask the bot questions about its feedback
SO THAT I understand the reasoning behind suggestions

US-006: Severity Classification
AS A developer
I WANT issues to be classified by severity
SO THAT I know which issues must be fixed vs nice-to-have
```

---

## 4. Kiến trúc hệ thống

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   GitHub    │    │    Slack    │    │   Jira/     │    │    LLM      │  │
│  │  (Webhooks) │    │    API      │    │   Linear    │    │  Providers  │  │
│  └──────┬──────┘    └──────▲──────┘    └──────▲──────┘    └──────▲──────┘  │
│         │                  │                  │                  │         │
└─────────┼──────────────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │                  │
          ▼                  │                  │                  │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         FastAPI Application                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │  Webhook    │  │   Webhook   │  │    Rate     │  │   Health    │  │  │
│  │  │  Receiver   │  │  Validator  │  │   Limiter   │  │   Checks    │  │  │
│  │  └──────┬──────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └─────────┼────────────────────────────────────────────────────────────┘  │
└────────────┼───────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MESSAGE QUEUE LAYER                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     Redis / RabbitMQ / Celery                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │   Review    │  │ Notification│  │   Retry     │  │    Dead     │  │  │
│  │  │   Queue     │  │    Queue    │  │   Queue     │  │   Letter    │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘  │  │
│  └─────────┼────────────────┼───────────────────────────────────────────┘  │
└────────────┼────────────────┼──────────────────────────────────────────────┘
             │                │
             ▼                │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH ENGINE (CORE)                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Stateful Graph Workflow                       │  │
│  │                                                                       │  │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │  │
│  │   │ Config  │───▶│ Context │───▶│ Context │───▶│  Route  │          │  │
│  │   │ Loader  │    │ Extract │    │ Enrich  │    │  Node   │          │  │
│  │   └─────────┘    └─────────┘    └─────────┘    └────┬────┘          │  │
│  │                                                      │               │  │
│  │          ┌───────────────────────────────────────────┼───────────┐  │  │
│  │          │               PARALLEL AGENTS             │           │  │  │
│  │          │  ┌─────────┐  ┌─────────┐  ┌─────────┐   │           │  │  │
│  │          │  │Security │  │  Style  │  │  Logic  │◀──┘           │  │  │
│  │          │  │ Agent   │  │  Agent  │  │  Agent  │               │  │  │
│  │          │  └────┬────┘  └────┬────┘  └────┬────┘               │  │  │
│  │          │       │            │            │                     │  │  │
│  │          │  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐               │  │  │
│  │          │  │  Perf   │  │  Docs   │  │  Test   │               │  │  │
│  │          │  │  Agent  │  │  Agent  │  │  Agent  │               │  │  │
│  │          │  └────┬────┘  └────┬────┘  └────┬────┘               │  │  │
│  │          └───────┼────────────┼────────────┼─────────────────────┘  │  │
│  │                  │            │            │                       │  │
│  │                  ▼            ▼            ▼                       │  │
│  │            ┌─────────────────────────────────────────┐             │  │
│  │            │         Review Aggregator & Critic       │             │  │
│  │            │     (Dedup, Filter, Severity Scoring)    │             │  │
│  │            └──────────────────┬──────────────────────┘             │  │
│  │                               │                                    │  │
│  │            ┌──────────────────┼──────────────────────┐             │  │
│  │            ▼                  ▼                      ▼             │  │
│  │   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │  │
│  │   │ GitHub Review  │  │ Slack Reporter │  │ Metrics Logger │      │  │
│  │   │   Publisher    │  │                │  │                │      │  │
│  │   └────────────────┘  └────────────────┘  └────────────────┘      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
             │                  │                      │
             ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DATA LAYER (🔮 PHASE 2/3 - NOT MVP)                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ PostgreSQL  │    │    Redis    │    │ VectorDB    │    │ Object      │  │
│  │ (Reviews,   │    │ (Cache,     │    │ (Embeddings │    │ Storage     │  │
│  │  Configs)   │    │  Sessions)  │    │  for RAG)   │    │ (Diffs)     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                              │
│  ⚠️ NOTE: Data Layer sẽ được implement sau khi MVP hoàn thành.              │
│  MVP sẽ sử dụng in-memory state và không persist data.                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Descriptions

| Component            | Responsibility                        | Tech Choice     | Phase   |
| -------------------- | ------------------------------------- | --------------- | ------- |
| **Webhook Receiver** | Tiếp nhận và validate GitHub webhooks | FastAPI         | **MVP** |
| **Message Queue**    | Async processing, retry handling      | Redis + Celery  | **MVP** |
| **LangGraph Engine** | Multi-agent orchestration             | LangGraph       | **MVP** |
| **Review Publisher** | Post comments to GitHub               | PyGithub/httpx  | **MVP** |
| **Slack Reporter**   | Send notifications                    | slack-sdk       | **MVP** |
| **Data Store**       | Persist reviews, configs              | PostgreSQL      | Phase 2 |
| **Cache Layer**      | Fast reads, session state             | Redis           | Phase 2 |
| **Vector Store**     | RAG for context retrieval             | Qdrant/Pinecone | Phase 3 |

---

## 5. Tech Stack đề xuất

### 5.1 Core Stack

> **⚠️ Lưu ý về Python version:** Python 3.13 là phiên bản stable mới nhất (released 10/2024). Python 3.14 vẫn đang trong giai đoạn beta và sẽ release vào 10/2025. Khuyến nghị sử dụng Python 3.13 cho stability.

```yaml
# ============================================
# MVP STACK (Phase 1)
# ============================================

Runtime & Framework:
  language: Python 3.13 # Latest stable (Oct 2024)
  framework: FastAPI 0.115.x
  async_runtime: uvicorn 0.32.x + asyncio
  package_manager: uv 0.5.x (10-100x faster than pip)

AI/ML Layer:
  orchestration: LangGraph 0.2.x # Pre-1.0, stable enough for MVP
  llm_framework: LangChain 0.3.x
  primary_llm: GPT-4o / Claude 3.5 Sonnet
  fallback_llm: GPT-4o-mini / Claude 3.5 Haiku
  embeddings: text-embedding-3-small # Phase 3 - for RAG

Message Queue & Background Tasks:
  broker: Redis 7.x
  task_queue: Celery 5.4.x
  # Note: MVP có thể bắt đầu synchronous,
  # chuyển sang Celery khi cần scale

GitHub Integration:
  api_client: httpx 0.28.x (async-first)
  webhook_validation: hmac-sha256
  auth: GitHub App (JWT + Installation Token)

Observability (MVP - Basic):
  logging: structlog 24.x + JSON
  error_tracking: Sentry 2.x

Infrastructure:
  container: Docker
  local_dev: Docker Compose
  cloud: Railway / Render (simple for MVP)

# ============================================
# PHASE 2/3 ADDITIONS (NOT MVP)
# ============================================

Database (Phase 2):
  primary: PostgreSQL 17
  cache: Redis 7.x (as cache, not just broker)

Vector Store (Phase 3 - RAG):
  vector_db: Qdrant (self-hosted) / Pinecone (managed)

Advanced Observability (Phase 2):
  tracing: OpenTelemetry
  metrics: Prometheus + Grafana

Production Infrastructure (Phase 2/3):
  orchestration: Kubernetes
  cloud: GCP Cloud Run / AWS ECS
  secrets: Vault / GCP Secret Manager
```

### 5.2 Rationale for Key Choices

#### 🐍 Why Python (FastAPI) over Node.js?

| Factor            | Python                    | Node.js                |
| ----------------- | ------------------------- | ---------------------- |
| LangGraph Support | ✅ Native, first-class    | ⚠️ JS port less mature |
| LLM Ecosystem     | ✅ Rich (LangChain, etc.) | ⚠️ Catching up         |
| Async Performance | ✅ Good with asyncio      | ✅ Excellent           |
| GitHub Libraries  | ✅ PyGithub, httpx        | ✅ Octokit             |
| Team Familiarity  | ❓ Depends                | ❓ Depends             |

**Recommendation:** Python + FastAPI for better LangGraph integration

#### 📊 Why LangGraph over alternatives?

| Framework          | Pros                                 | Cons                    |
| ------------------ | ------------------------------------ | ----------------------- |
| **LangGraph**      | Native state, branching, persistence | Steeper learning curve  |
| **AutoGen**        | Easy multi-agent                     | Less control over flow  |
| **CrewAI**         | Simple to start                      | Limited customization   |
| **Pure LangChain** | Flexible                             | No built-in graph state |

**Recommendation:** LangGraph - best fit for complex, stateful workflows

#### 🗄️ Why PostgreSQL + Redis?

- **PostgreSQL**: ACID compliance for review results, JSONB for flexible schemas
- **Redis**: Fast caching, session storage, Celery broker, real-time features

### 5.3 Dependencies (pyproject.toml)

```toml
[project]
name = "ai-code-reviewer"
version = "0.1.0"
requires-python = ">=3.13"

dependencies = [
    # ============================================
    # MVP DEPENDENCIES
    # ============================================

    # Web Framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",

    # AI/LLM (Core)
    "langgraph>=0.2.55",
    "langchain>=0.3.13",
    "langchain-openai>=0.2.14",
    "langchain-anthropic>=0.3.0",

    # GitHub Integration
    "httpx>=0.28.0",
    "PyJWT>=2.10.0",        # For GitHub App auth
    "cryptography>=44.0.0", # For private key handling

    # Background Tasks (MVP - simple)
    "celery[redis]>=5.4.0",
    "redis>=5.2.0",

    # Notifications
    "slack-sdk>=3.33.0",

    # Utilities
    "structlog>=24.4.0",
    "python-dotenv>=1.0.0",
    "tenacity>=9.0.0",      # Retry logic
    "pyyaml>=6.0.0",        # Config parsing

    # Observability (Basic for MVP)
    "sentry-sdk[fastapi]>=2.19.0",
]

[project.optional-dependencies]
# ============================================
# PHASE 2 DEPENDENCIES (Install when needed)
# ============================================
phase2 = [
    # Database
    "asyncpg>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "alembic>=1.14.0",

    # Advanced Observability
    "opentelemetry-api>=1.28.0",
    "opentelemetry-sdk>=1.28.0",
    "opentelemetry-instrumentation-fastapi>=0.49b0",
]

# ============================================
# PHASE 3 DEPENDENCIES (Install when needed)
# ============================================
phase3 = [
    # Vector Store for RAG
    "qdrant-client>=1.12.0",
    "langchain-community>=0.3.13",  # For embeddings
]

dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "pre-commit>=4.0.0",
]
```

---

## 5.4 Project Structure

> 🏗️ **Cấu trúc thư mục đề xuất cho MVP**

```
ai-code-reviewer/
├── 📁 src/
│   ├── 📁 app/                      # FastAPI Application
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── config.py                # Pydantic Settings
│   │   ├── dependencies.py          # Dependency injection
│   │   │
│   │   ├── 📁 api/                  # API Layer
│   │   │   ├── __init__.py
│   │   │   ├── 📁 v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── webhooks.py      # GitHub webhook handlers
│   │   │   │   ├── reviews.py       # Review status endpoints
│   │   │   │   └── health.py        # Health check endpoints
│   │   │   └── router.py            # API router aggregation
│   │   │
│   │   ├── 📁 models/               # Pydantic Models
│   │   │   ├── __init__.py
│   │   │   ├── github.py            # GitHub webhook payloads
│   │   │   ├── review.py            # Review comments, findings
│   │   │   └── config.py            # Repository config schema
│   │   │
│   │   └── 📁 services/             # Business Logic Services
│   │       ├── __init__.py
│   │       ├── github_service.py    # GitHub API interactions
│   │       ├── slack_service.py     # Slack notifications
│   │       └── webhook_validator.py # Signature verification
│   │
│   ├── 📁 agents/                   # LangGraph Agents
│   │   ├── __init__.py
│   │   ├── graph.py                 # Main graph definition
│   │   ├── state.py                 # GraphState TypedDict
│   │   │
│   │   ├── 📁 nodes/                # Individual graph nodes
│   │   │   ├── __init__.py
│   │   │   ├── config_loader.py
│   │   │   ├── context_extractor.py
│   │   │   ├── security_agent.py
│   │   │   ├── style_agent.py
│   │   │   ├── logic_agent.py
│   │   │   ├── review_aggregator.py
│   │   │   ├── github_publisher.py
│   │   │   └── slack_reporter.py
│   │   │
│   │   └── 📁 prompts/              # LLM Prompt templates
│   │       ├── __init__.py
│   │       ├── security.py
│   │       ├── style.py
│   │       ├── logic.py
│   │       └── summary.py
│   │
│   ├── 📁 core/                     # Core utilities
│   │   ├── __init__.py
│   │   ├── llm.py                   # LLM client configuration
│   │   ├── logging.py               # Structlog setup
│   │   └── exceptions.py            # Custom exceptions
│   │
│   └── 📁 workers/                  # Background tasks (Celery)
│       ├── __init__.py
│       ├── celery_app.py            # Celery configuration
│       └── tasks.py                 # Async task definitions
│
├── 📁 tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── 📁 unit/
│   │   ├── test_webhook_validator.py
│   │   ├── test_agents/
│   │   └── test_services/
│   ├── 📁 integration/
│   │   ├── test_github_webhook.py
│   │   └── test_langgraph_flow.py
│   └── 📁 e2e/
│       └── test_full_review_flow.py
│
├── 📁 scripts/                      # Utility scripts
│   ├── setup_github_app.py          # GitHub App setup helper
│   └── test_webhook.py              # Local webhook testing
│
├── 📁 docker/
│   ├── Dockerfile                   # Production Dockerfile
│   ├── Dockerfile.dev               # Development Dockerfile
│   └── docker-compose.yml           # Local dev environment
│
├── 📁 docs/
│   ├── ARCHITECTURE.md
│   ├── SETUP.md
│   └── API.md
│
├── .env.example                     # Environment variables template
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml                   # Project config & dependencies
├── README.md
└── Makefile                         # Common commands
```

### 5.5 Key Files Explained

| File                        | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `src/app/main.py`           | FastAPI app initialization, middleware, lifespan |
| `src/agents/graph.py`       | LangGraph workflow definition                    |
| `src/agents/state.py`       | Shared state schema for all nodes                |
| `src/agents/nodes/*.py`     | Individual node implementations                  |
| `src/workers/celery_app.py` | Celery app for background processing             |
| `docker-compose.yml`        | Redis + App for local development                |

---

## 6. Chi tiết thiết kế LangGraph

### 6.1 State Schema

```python
from typing import TypedDict, Annotated, Sequence, Optional, Literal
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from datetime import datetime


class FileChange(BaseModel):
    """Represents a single file change in the PR."""
    filename: str
    status: Literal["added", "modified", "removed", "renamed"]
    additions: int
    deletions: int
    patch: str  # Git diff patch
    language: Optional[str] = None


class ReviewComment(BaseModel):
    """A single review comment."""
    id: str
    file: str
    line: int
    severity: Literal["critical", "warning", "info", "suggestion"]
    category: str  # security, style, logic, performance, etc.
    message: str
    suggestion: Optional[str] = None  # Code suggestion if applicable
    confidence: float = Field(ge=0.0, le=1.0)
    agent_source: str  # Which agent generated this


class PRMetadata(BaseModel):
    """Metadata about the Pull Request."""
    owner: str
    repo: str
    pr_number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    created_at: datetime
    labels: list[str]


class ReviewConfig(BaseModel):
    """Per-repository configuration."""
    ignore_patterns: list[str] = Field(default_factory=lambda: [
        "*.lock", "*.min.js", "*.min.css",
        "vendor/*", "node_modules/*", "dist/*"
    ])
    enabled_agents: list[str] = Field(default_factory=lambda: [
        "security", "style", "logic", "performance", "documentation"
    ])
    severity_threshold: Literal["critical", "warning", "info"] = "info"
    max_comments_per_file: int = 10
    custom_rules: dict = Field(default_factory=dict)


class GraphState(TypedDict):
    """Main state object for the LangGraph workflow."""

    # Input
    pr_metadata: PRMetadata
    config: ReviewConfig

    # Context Extraction
    file_changes: list[FileChange]
    total_additions: int
    total_deletions: int
    affected_modules: list[str]

    # Enrichment
    related_issues: list[dict]
    recent_reviews: list[dict]  # Historical context

    # Agent Outputs (Annotated for parallel merge)
    agent_comments: Annotated[list[ReviewComment], operator.add]

    # Aggregated Results
    final_comments: list[ReviewComment]
    summary: str
    overall_score: float  # 0-100

    # Publishing Status
    github_review_id: Optional[int]
    slack_message_ts: Optional[str]

    # Metadata
    started_at: datetime
    completed_at: Optional[datetime]
    errors: list[str]
```

### 6.2 Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator


def create_review_graph() -> StateGraph:
    """Create the main review workflow graph."""

    # Initialize graph with state schema
    workflow = StateGraph(GraphState)

    # ============================================
    # NODE DEFINITIONS
    # ============================================

    # Node 1: Load Configuration
    workflow.add_node("config_loader", config_loader_node)

    # Node 2: Extract Context from PR
    workflow.add_node("context_extractor", context_extractor_node)

    # Node 3: Enrich Context (issues, history)
    workflow.add_node("context_enricher", context_enricher_node)

    # Node 4: Router (decides which agents to run)
    workflow.add_node("agent_router", agent_router_node)

    # Node 5-10: Parallel Review Agents
    workflow.add_node("security_agent", security_agent_node)
    workflow.add_node("style_agent", style_agent_node)
    workflow.add_node("logic_agent", logic_agent_node)
    workflow.add_node("performance_agent", performance_agent_node)
    workflow.add_node("documentation_agent", documentation_agent_node)
    workflow.add_node("test_coverage_agent", test_coverage_agent_node)

    # Node 11: Aggregate and Filter
    workflow.add_node("review_aggregator", review_aggregator_node)

    # Node 12: Publish to GitHub
    workflow.add_node("github_publisher", github_publisher_node)

    # Node 13: Send Slack Notification
    workflow.add_node("slack_reporter", slack_reporter_node)

    # ============================================
    # EDGE DEFINITIONS
    # ============================================

    # Entry point
    workflow.set_entry_point("config_loader")

    # Sequential flow for setup
    workflow.add_edge("config_loader", "context_extractor")
    workflow.add_edge("context_extractor", "context_enricher")
    workflow.add_edge("context_enricher", "agent_router")

    # Conditional branching to parallel agents
    def route_to_agents(state: GraphState) -> list[str]:
        """Route to enabled agents based on config."""
        enabled = state["config"].enabled_agents
        agent_map = {
            "security": "security_agent",
            "style": "style_agent",
            "logic": "logic_agent",
            "performance": "performance_agent",
            "documentation": "documentation_agent",
            "test_coverage": "test_coverage_agent",
        }
        return [agent_map[a] for a in enabled if a in agent_map]

    # Fan-out to parallel agents
    workflow.add_conditional_edges(
        "agent_router",
        route_to_agents,
        {
            "security_agent": "security_agent",
            "style_agent": "style_agent",
            "logic_agent": "logic_agent",
            "performance_agent": "performance_agent",
            "documentation_agent": "documentation_agent",
            "test_coverage_agent": "test_coverage_agent",
        }
    )

    # Fan-in: All agents converge to aggregator
    workflow.add_edge("security_agent", "review_aggregator")
    workflow.add_edge("style_agent", "review_aggregator")
    workflow.add_edge("logic_agent", "review_aggregator")
    workflow.add_edge("performance_agent", "review_aggregator")
    workflow.add_edge("documentation_agent", "review_aggregator")
    workflow.add_edge("test_coverage_agent", "review_aggregator")

    # Final stages (can be parallel)
    workflow.add_edge("review_aggregator", "github_publisher")
    workflow.add_edge("review_aggregator", "slack_reporter")

    # End conditions
    workflow.add_edge("github_publisher", END)
    workflow.add_edge("slack_reporter", END)

    return workflow


# Compile with checkpointing for persistence
memory = MemorySaver()
graph = create_review_graph().compile(checkpointer=memory)
```

### 6.3 Node Implementations

#### Node 1: Config Loader

```python
async def config_loader_node(state: GraphState) -> dict:
    """Load repository-specific configuration."""
    owner = state["pr_metadata"].owner
    repo = state["pr_metadata"].repo

    # Try to fetch .ai-reviewer.yaml from repo
    config = await fetch_repo_config(owner, repo)

    if config is None:
        config = ReviewConfig()  # Use defaults

    return {"config": config}
```

#### Node 2: Context Extractor

```python
async def context_extractor_node(state: GraphState) -> dict:
    """Fetch and process PR diff from GitHub."""
    meta = state["pr_metadata"]
    config = state["config"]

    # Fetch PR files from GitHub API
    raw_files = await github_client.get_pr_files(
        meta.owner, meta.repo, meta.pr_number
    )

    # Filter out ignored files
    file_changes = []
    for f in raw_files:
        if not should_ignore(f.filename, config.ignore_patterns):
            file_changes.append(FileChange(
                filename=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                patch=f.patch or "",
                language=detect_language(f.filename)
            ))

    # Calculate totals
    total_additions = sum(f.additions for f in file_changes)
    total_deletions = sum(f.deletions for f in file_changes)

    # Identify affected modules
    affected_modules = list(set(
        f.filename.split("/")[0] for f in file_changes
    ))

    return {
        "file_changes": file_changes,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "affected_modules": affected_modules,
    }
```

#### Node 5: Security Agent (Example)

```python
async def security_agent_node(state: GraphState) -> dict:
    """Analyze code for security vulnerabilities."""

    comments = []

    for file in state["file_changes"]:
        if not file.patch:
            continue

        # Build prompt with context
        prompt = SECURITY_REVIEW_PROMPT.format(
            filename=file.filename,
            language=file.language,
            diff=file.patch,
            custom_rules=state["config"].custom_rules.get("security", "")
        )

        # Call LLM
        response = await llm.ainvoke(prompt)

        # Parse structured output
        findings = parse_security_findings(response)

        for finding in findings:
            comments.append(ReviewComment(
                id=generate_id(),
                file=file.filename,
                line=finding.line,
                severity=finding.severity,
                category="security",
                message=finding.message,
                suggestion=finding.fix,
                confidence=finding.confidence,
                agent_source="security_agent"
            ))

    return {"agent_comments": comments}
```

#### Node 11: Review Aggregator

```python
async def review_aggregator_node(state: GraphState) -> dict:
    """Aggregate, deduplicate, and filter review comments."""

    all_comments = state["agent_comments"]
    config = state["config"]

    # Step 1: Deduplicate similar comments
    unique_comments = deduplicate_comments(all_comments)

    # Step 2: Use Senior LLM to validate and filter
    validated_comments = await validate_with_senior_llm(
        unique_comments,
        state["file_changes"]
    )

    # Step 3: Filter by severity threshold
    severity_order = ["critical", "warning", "info", "suggestion"]
    threshold_idx = severity_order.index(config.severity_threshold)

    filtered_comments = [
        c for c in validated_comments
        if severity_order.index(c.severity) <= threshold_idx
    ]

    # Step 4: Limit comments per file
    final_comments = limit_per_file(
        filtered_comments,
        config.max_comments_per_file
    )

    # Step 5: Generate summary
    summary = await generate_review_summary(
        final_comments,
        state["pr_metadata"],
        state["total_additions"],
        state["total_deletions"]
    )

    # Step 6: Calculate overall score
    score = calculate_quality_score(final_comments)

    return {
        "final_comments": final_comments,
        "summary": summary,
        "overall_score": score,
    }
```

### 6.4 Graph Visualization

```
                    ┌─────────────────┐
                    │  config_loader  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │context_extractor│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │context_enricher │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  agent_router   │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │ security  │    │   style   │    │   logic   │
    │   agent   │    │   agent   │    │   agent   │
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
          │  ┌─────────────┼─────────────┐  │
          │  │             │             │  │
          │  ▼             ▼             ▼  │
          │ ┌───────────┬───────────┬───────────┐
          │ │performance│ docs      │test_cover │
          │ │   agent   │   agent   │  agent    │
          │ └─────┬─────┴─────┬─────┴─────┬─────┘
          │       │           │           │
          └───────┴───────────┴───────────┘
                        │
                        ▼
              ┌─────────────────┐
              │review_aggregator│
              └────────┬────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
    ┌───────────────┐    ┌───────────────┐
    │github_publisher│    │slack_reporter │
    └───────────────┘    └───────────────┘
            │                     │
            ▼                     ▼
           END                   END
```

---

## 7. Tính năng chi tiết

### 7.1 MVP Features (Phase 1)

| Feature                 | Description                          | Priority |
| ----------------------- | ------------------------------------ | -------- |
| **Webhook Integration** | Receive GitHub PR events             | P0       |
| **Basic Review**        | Security + Style + Logic agents      | P0       |
| **Line Comments**       | Post inline comments on PR           | P0       |
| **Severity Levels**     | Critical/Warning/Info classification | P0       |
| **PR Summary**          | Auto-generated summary comment       | P0       |
| **Slack Basic**         | Simple PR notification               | P1       |

### 7.2 Enhanced Features (Phase 2)

| Feature                | Description                       | Priority |
| ---------------------- | --------------------------------- | -------- |
| **Custom Rules**       | YAML-based config per repo        | P1       |
| **Incremental Review** | Review only new commits           | P1       |
| **Interactive Chat**   | Bot responds to @mentions         | P1       |
| **Code Suggestions**   | One-click apply fixes             | P2       |
| **Review History**     | Store and learn from past reviews | P2       |

### 7.3 Advanced Features (Phase 3)

| Feature                  | Description                         | Priority |
| ------------------------ | ----------------------------------- | -------- |
| **RAG Context**          | Use codebase embeddings for context | P2       |
| **Issue Integration**    | Link to Jira/Linear tickets         | P2       |
| **Quality Dashboard**    | Metrics and trends visualization    | P3       |
| **Multi-repo Analytics** | Cross-repo insights                 | P3       |
| **Custom Agent Builder** | UI to create custom agents          | P3       |

---

## 8. API Specifications

### 8.1 Webhook Endpoint

```python
# POST /webhooks/github
from fastapi import FastAPI, Request, HTTPException, Header
import hmac
import hashlib

app = FastAPI()

@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None),
):
    """
    Receive GitHub webhook events.

    Supported events:
    - pull_request: opened, synchronize, reopened
    - issue_comment: created (for @bot mentions)
    """

    # 1. Validate signature
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse payload
    payload = await request.json()

    # 3. Check for duplicate delivery
    if await is_duplicate_delivery(x_github_delivery):
        return {"status": "duplicate"}

    # 4. Handle event
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            # Queue review task
            task = review_pr.delay(
                owner=payload["repository"]["owner"]["login"],
                repo=payload["repository"]["name"],
                pr_number=payload["pull_request"]["number"],
                delivery_id=x_github_delivery,
            )
            return {"status": "queued", "task_id": task.id}

    elif x_github_event == "issue_comment":
        if is_bot_mention(payload):
            task = handle_bot_mention.delay(payload)
            return {"status": "queued", "task_id": task.id}

    return {"status": "ignored"}


def verify_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not signature:
        return False

    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    expected = "sha256=" + hmac.new(
        secret, body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

### 8.2 Configuration Schema

```yaml
# .ai-reviewer.yaml (placed in repository root)

# Version of config schema
version: "1.0"

# Files/patterns to ignore
ignore:
  - "*.lock"
  - "*.min.js"
  - "*.min.css"
  - "vendor/**"
  - "node_modules/**"
  - "dist/**"
  - "**/__snapshots__/**"

# Enabled review agents
agents:
  security:
    enabled: true
    severity_threshold: warning # Only report warning+

  style:
    enabled: true
    severity_threshold: info

  logic:
    enabled: true
    severity_threshold: warning

  performance:
    enabled: true
    severity_threshold: warning

  documentation:
    enabled: false # Disabled for this repo

  test_coverage:
    enabled: true
    min_coverage_delta: -5 # Alert if coverage drops >5%

# Custom rules (added to agent prompts)
custom_rules:
  security: |
    - Always validate user input
    - Use parameterized queries for SQL
    - No hardcoded secrets

  style: |
    - Use TypeScript strict mode
    - Max function length: 50 lines
    - Prefer async/await over .then()

# Notification settings
notifications:
  slack:
    enabled: true
    channel: "#pr-reviews"
    mention_on_critical: true

# Comment settings
comments:
  max_per_file: 10
  max_total: 50
  include_suggestions: true
  summary_position: "top" # or "bottom"

# Language-specific settings
languages:
  python:
    line_length: 88
    docstring_style: google

  typescript:
    strict_null_checks: true
```

### 8.3 Internal APIs

```python
# Review status API
@app.get("/api/v1/reviews/{review_id}")
async def get_review_status(review_id: str):
    """Get status of a review task."""
    return {
        "id": review_id,
        "status": "completed",  # pending, running, completed, failed
        "pr": {
            "owner": "example",
            "repo": "project",
            "number": 123
        },
        "metrics": {
            "total_comments": 15,
            "by_severity": {
                "critical": 2,
                "warning": 5,
                "info": 8
            },
            "quality_score": 75.5,
            "processing_time_ms": 45000
        },
        "created_at": "2024-12-21T08:00:00Z",
        "completed_at": "2024-12-21T08:00:45Z"
    }


# Force re-review
@app.post("/api/v1/reviews/{review_id}/rerun")
async def rerun_review(review_id: str):
    """Trigger a re-review of a PR."""
    pass


# Get repository config
@app.get("/api/v1/repos/{owner}/{repo}/config")
async def get_repo_config(owner: str, repo: str):
    """Get effective configuration for a repository."""
    pass
```

---

## 9. Bảo mật & Compliance

### 9.1 Security Requirements

| Requirement            | Implementation                       |
| ---------------------- | ------------------------------------ |
| **Webhook Validation** | HMAC-SHA256 signature verification   |
| **Secret Management**  | Vault / GCP Secret Manager           |
| **API Authentication** | GitHub App Installation Tokens       |
| **Data Encryption**    | TLS 1.3 in transit, AES-256 at rest  |
| **Access Control**     | Installation-scoped permissions      |
| **Audit Logging**      | All actions logged with user context |

### 9.2 GitHub App Permissions

```yaml
# Minimum required permissions
permissions:
  contents: read # Read code content
  pull_requests: write # Post reviews and comments
  issues: write # For @bot interactions
  metadata: read # Repository metadata

# Webhook events to subscribe
events:
  - pull_request
  - issue_comment
```

### 9.3 Data Handling

| Data Type       | Retention  | Storage     |
| --------------- | ---------- | ----------- |
| PR Diffs        | 7 days     | Redis/S3    |
| Review Comments | 90 days    | PostgreSQL  |
| Metrics         | Indefinite | PostgreSQL  |
| User Data       | N/A        | Not stored  |
| Source Code     | Not stored | Memory only |

---

## 10. Kế hoạch triển khai

### 10.1 Phase 1: MVP (4 tuần)

```
Week 1: Foundation
├── [ ] Project setup (FastAPI, Docker, CI/CD)
├── [ ] GitHub App registration
├── [ ] Webhook receiver with validation
└── [ ] Basic LangGraph skeleton

Week 2: Core Agents
├── [ ] Context Extractor node
├── [ ] Security Agent
├── [ ] Style Agent
└── [ ] Logic Agent

Week 3: Integration
├── [ ] Review Aggregator
├── [ ] GitHub Publisher (line comments)
├── [ ] Basic Slack notification
└── [ ] Error handling

Week 4: Polish & Deploy
├── [ ] Testing (unit + integration)
├── [ ] Documentation
├── [ ] Deploy to staging
└── [ ] Internal dogfooding
```

### 10.2 Phase 2: Enhanced (4 tuần)

```
Week 5-6: Features
├── [ ] YAML configuration support
├── [ ] Incremental review
├── [ ] Interactive chat (@bot mentions)
└── [ ] More agents (Performance, Docs)

Week 7-8: Quality
├── [ ] Improved prompts
├── [ ] False positive reduction
├── [ ] Performance optimization
└── [ ] Monitoring dashboard
```

### 10.3 Phase 3: Scale (4 tuần)

```
Week 9-12:
├── [ ] Vector DB for RAG context
├── [ ] Multi-repository analytics
├── [ ] Custom agent builder
└── [ ] Enterprise features
```

---

## 11. Metrics & KPIs

### 11.1 Success Metrics

| Metric                   | Target             | Measurement       |
| ------------------------ | ------------------ | ----------------- |
| **Review Latency**       | < 5 min for avg PR | P95 latency       |
| **False Positive Rate**  | < 15%              | User dismiss rate |
| **Issue Detection Rate** | 80% of true issues | Manual audit      |
| **Adoption Rate**        | 90% of PRs         | Webhook coverage  |
| **User Satisfaction**    | > 4.0/5.0          | Survey            |

### 11.2 Operational Metrics

| Metric                  | Alert Threshold |
| ----------------------- | --------------- |
| API Error Rate          | > 1%            |
| Webhook Processing Time | > 30s           |
| Queue Depth             | > 100 items     |
| LLM Token Usage         | Budget limit    |
| GitHub API Rate Limit   | > 80% used      |

---

## 12. Rủi ro & Giải pháp

### 12.1 Technical Risks

| Risk                      | Impact                      | Mitigation                                   |
| ------------------------- | --------------------------- | -------------------------------------------- |
| **LLM Hallucinations**    | False positives annoy users | Senior LLM validation, confidence thresholds |
| **Large PR Handling**     | Timeout, high cost          | Chunking, file prioritization                |
| **GitHub Rate Limits**    | Service degradation         | Caching, request batching                    |
| **Context Window Limits** | Incomplete analysis         | Smart summarization, RAG                     |

### 12.2 Business Risks

| Risk                  | Impact          | Mitigation                      |
| --------------------- | --------------- | ------------------------------- |
| **LLM Cost Overrun**  | Budget exceeded | Usage monitoring, tiered models |
| **Low Adoption**      | Wasted effort   | Early user feedback, dogfooding |
| **Security Concerns** | Trust issues    | SOC 2 compliance, transparency  |

---

## 📝 Appendix

### A. Prompt Templates

````python
SECURITY_REVIEW_PROMPT = """
You are a security expert reviewing code changes. Analyze the following diff for security vulnerabilities.

## File: {filename}
## Language: {language}

## Diff:
```diff
{diff}
````

## Custom Security Rules:

{custom_rules}

## Instructions:

1. Identify potential security issues
2. For each issue, specify:
   - Line number (from the diff, lines starting with '+')
   - Severity (critical/warning/info)
   - Clear explanation
   - Suggested fix if applicable
3. Consider: SQL injection, XSS, hardcoded secrets, authentication flaws, etc.
4. Only report issues with >70% confidence

## Output Format (JSON):

{
"findings": [
{
"line": 42,
"severity": "critical",
"message": "Potential SQL injection vulnerability",
"fix": "Use parameterized query",
"confidence": 0.95
}
]
}
"""

````

### B. Environment Variables

```bash
# .env.example

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/secrets/github-app.pem
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/reviewer
REDIS_URL=redis://localhost:6379/0

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...

# Observability
SENTRY_DSN=https://...
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Feature Flags
ENABLE_RAG_CONTEXT=false
MAX_PARALLEL_AGENTS=6
````

---

## ✅ Kết luận

Bản phác thảo của bạn đã capture được các thành phần cốt lõi rất tốt.

### MVP Focus (Phase 1)

Để hoàn thành MVP nhanh chóng, chúng ta sẽ **KHÔNG implement** các thành phần sau trong phase đầu:

| Component           | Lý do defer              | Thay thế MVP                    |
| ------------------- | ------------------------ | ------------------------------- |
| **PostgreSQL**      | Chưa cần persist         | In-memory state                 |
| **Redis Cache**     | Overhead không cần thiết | Redis chỉ làm broker cho Celery |
| **Vector DB / RAG** | Feature nâng cao         | Simple context từ diff          |
| **OpenTelemetry**   | Complex setup            | Structlog + Sentry              |

### Tech Stack Summary

**MVP (Phase 1):**

- **Runtime:** Python 3.13 (latest stable)
- **Framework:** FastAPI 0.115.x
- **Agent Orchestration:** LangGraph 0.2.x
- **LLM:** GPT-4o / Claude 3.5 Sonnet
- **Queue:** Redis + Celery (async processing)
- **Infrastructure:** Docker + Railway/Render

**Phase 2 additions:**

- PostgreSQL (data persistence)
- Redis Cache (performance)
- OpenTelemetry (observability)

**Phase 3 additions:**

- Vector DB + RAG (context retrieval)
- Kubernetes (scale)

---

## 📋 Next Steps

1. [ ] Setup project structure
2. [ ] Register GitHub App
3. [ ] Implement webhook receiver
4. [ ] Build first LangGraph agent (Security)
5. [ ] Test end-to-end flow

Bạn có muốn mình bắt đầu implement MVP không?
