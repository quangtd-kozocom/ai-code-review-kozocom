# 08 - Environment & Dependencies

## 🔧 Required Services

### 1. Neon PostgreSQL (Free Tier)

**Sign up:** https://neon.tech

| Limit    | Free Tier               |
| -------- | ----------------------- |
| Storage  | 512 MB                  |
| Projects | 3                       |
| Compute  | Unlimited (scales to 0) |
| Branches | 10                      |

**Setup:**

1. Create project → Choose region (us-east-1 recommended)
2. Copy connection string
3. Add to `.env`

```env
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

---

### 2. Upstash Redis (Free Tier)

**Sign up:** https://upstash.com

| Limit     | Free Tier  |
| --------- | ---------- |
| Commands  | 10,000/day |
| Storage   | 256 MB     |
| Databases | 1          |

**Setup:**

1. Create database → Choose region close to server
2. Copy Redis URL (REST or native)
3. Add to `.env`

```env
UPSTASH_REDIS_URL=redis://default:xxx@global-xxx.upstash.io:6379
```

---

## 📦 Dependencies

### pyproject.toml

```toml
[project]
name = "ai-code-reviewer"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # ═══════════════════════════════════════════════════
    # Framework
    # ═══════════════════════════════════════════════════
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",

    # ═══════════════════════════════════════════════════
    # Database - SQLModel (ORM)
    # ═══════════════════════════════════════════════════
    # SQLModel includes SQLAlchemy + Pydantic
    "sqlmodel>=0.0.14",
    # Async PostgreSQL driver
    "asyncpg>=0.29.0",

    # ═══════════════════════════════════════════════════
    # Cache - Redis
    # ═══════════════════════════════════════════════════
    # redis-py with hiredis C extension for speed
    "redis[hiredis]>=5.0.0",

    # ═══════════════════════════════════════════════════
    # Validation & Config
    # ═══════════════════════════════════════════════════
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0.1",

    # ═══════════════════════════════════════════════════
    # HTTP Client
    # ═══════════════════════════════════════════════════
    "httpx>=0.26.0",

    # ═══════════════════════════════════════════════════
    # LLM
    # ═══════════════════════════════════════════════════
    "langchain>=0.1.0",
    "langchain-openai>=0.0.5",
    "langgraph>=0.0.20",

    # ═══════════════════════════════════════════════════
    # Task Queue
    # ═══════════════════════════════════════════════════
    "celery[redis]>=5.3.0",

    # ═══════════════════════════════════════════════════
    # Logging & Monitoring
    # ═══════════════════════════════════════════════════
    "structlog>=24.1.0",

    # ═══════════════════════════════════════════════════
    # Security
    # ═══════════════════════════════════════════════════
    "pyjwt[crypto]>=2.8.0",
    "cryptography>=41.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]
```

### Install Commands

```bash
# Using pip
pip install sqlmodel asyncpg "redis[hiredis]" pyyaml

# Using poetry
poetry add sqlmodel asyncpg "redis[hiredis]" pyyaml

# Using uv (faster)
uv pip install sqlmodel asyncpg "redis[hiredis]" pyyaml
```

---

## 📄 Environment Variables

### .env Template

```env
# ═══════════════════════════════════════════════════════════
# APPLICATION
# ═══════════════════════════════════════════════════════════
DEBUG=false
LOG_LEVEL=INFO
APP_URL=https://your-app.com

# ═══════════════════════════════════════════════════════════
# GITHUB APP
# ═══════════════════════════════════════════════════════════
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# ═══════════════════════════════════════════════════════════
# LLM PROVIDER
# ═══════════════════════════════════════════════════════════
OPENROUTER_API_KEY=sk-or-xxx
OPENROUTER_DEFAULT_MODEL=xiaomi/mimo-v2-flash:free

# ═══════════════════════════════════════════════════════════
# CELERY REDIS (existing)
# ═══════════════════════════════════════════════════════════
REDIS_URL=redis://localhost:6379

# ═══════════════════════════════════════════════════════════
# DATABASE - Neon PostgreSQL (NEW)
# ═══════════════════════════════════════════════════════════
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# ═══════════════════════════════════════════════════════════
# CACHE - Upstash Redis (NEW)
# ═══════════════════════════════════════════════════════════
UPSTASH_REDIS_URL=redis://default:xxx@global-xxx.upstash.io:6379

# ═══════════════════════════════════════════════════════════
# CONFIG SETTINGS (NEW)
# ═══════════════════════════════════════════════════════════
CONFIG_CACHE_TTL=300
```

---

## ⚙️ Updated Settings Class

### File: `src/app/config.py`

```python
"""
Application settings from environment variables.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # ═══════════════════════════════════════════════════
    # Application
    # ═══════════════════════════════════════════════════
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_URL: Optional[str] = None

    # ═══════════════════════════════════════════════════
    # GitHub App
    # ═══════════════════════════════════════════════════
    GITHUB_APP_ID: int
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str

    # ═══════════════════════════════════════════════════
    # LLM
    # ═══════════════════════════════════════════════════
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_DEFAULT_MODEL: str = "xiaomi/mimo-v2-flash:free"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════
    # Celery Redis
    # ═══════════════════════════════════════════════════
    REDIS_URL: str

    # ═══════════════════════════════════════════════════
    # Slack
    # ═══════════════════════════════════════════════════
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_CHANNEL: str = "#pr-reviews"

    # ═══════════════════════════════════════════════════
    # Sentry
    # ═══════════════════════════════════════════════════
    SENTRY_DSN: Optional[str] = None

    # ═══════════════════════════════════════════════════
    # Database - Neon PostgreSQL (NEW)
    # ═══════════════════════════════════════════════════
    DATABASE_URL: Optional[str] = None

    # ═══════════════════════════════════════════════════
    # Cache - Upstash Redis (NEW)
    # ═══════════════════════════════════════════════════
    UPSTASH_REDIS_URL: Optional[str] = None

    # ═══════════════════════════════════════════════════
    # Config System (NEW)
    # ═══════════════════════════════════════════════════
    CONFIG_CACHE_TTL: int = 300  # 5 minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

---

## 🚀 App Lifecycle

### File: `src/app/main.py`

```python
"""
FastAPI application with proper lifecycle management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
import structlog

from ..core.database import init_db, close_db
from ..core.redis import close_redis

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management.

    Startup: Initialize database tables
    Shutdown: Close connections
    """
    # Startup
    log.info("Application starting...")

    try:
        await init_db()
        log.info("Database initialized")
    except Exception as e:
        log.warning("Database init failed", error=str(e))

    yield

    # Shutdown
    log.info("Application shutting down...")
    await close_db()
    await close_redis()
    log.info("Connections closed")


# Create app with lifespan
app = FastAPI(
    title="AI Code Reviewer",
    version="0.1.0",
    lifespan=lifespan,
)
```

---

## 🧪 Local Development (Without External Services)

For development without Neon/Upstash, the system degrades gracefully:

```python
# In service.py - graceful degradation
async def get_config(self, owner, repo):
    # 1. Try cache (skip if no Redis configured)
    if self.cache:
        try:
            cached = await self.cache.get(owner, repo)
            if cached:
                return ReviewerConfig(**cached)
        except Exception:
            pass  # Redis not available

    # 2. Try GitHub
    config_dict = await self.loader.load(owner, repo)
    if config_dict:
        return ReviewerConfig(**config_dict)

    # 3. Try database (skip if not configured)
    if self.repository:
        try:
            db_config = await self.repository.get(owner, repo)
            if db_config:
                return ReviewerConfig(**db_config.config_data)
        except Exception:
            pass  # DB not available

    # 4. Defaults always work
    return ReviewerConfig()
```

---

## ✅ Setup Checklist

### External Services

- [ ] Create Neon account & project
- [ ] Copy DATABASE_URL to .env
- [ ] Create Upstash account & database
- [ ] Copy UPSTASH_REDIS_URL to .env

### Dependencies

- [ ] Add sqlmodel, asyncpg, redis to pyproject.toml
- [ ] Run `pip install -e .` or `poetry install`

### Code Setup

- [ ] Update Settings class with new fields
- [ ] Create `src/core/database.py`
- [ ] Create `src/core/redis.py`
- [ ] Update app lifespan

### Database

- [ ] Run `python scripts/migrate_db.py`
