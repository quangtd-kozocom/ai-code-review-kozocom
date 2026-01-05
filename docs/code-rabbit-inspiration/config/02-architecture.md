# 02 - Architecture & Tech Stack

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           GITHUB REPOSITORY                              │
│   ┌─────────────────┐                                                   │
│   │ .reviewer.yaml  │                                                   │
│   └────────┬────────┘                                                   │
└────────────┼────────────────────────────────────────────────────────────┘
             │
             │ (1) Fetch on PR event
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI REVIEWER SERVICE                               │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                      ConfigService                                │  │
│   │                                                                   │  │
│   │   ┌─────────┐    ┌─────────────┐    ┌─────────────────────────┐  │  │
│   │   │ GitHub  │───▶│   Loader    │───▶│  Merge & Validate       │  │  │
│   │   │  API    │    │ (YAML file) │    │  (SQLModel/Pydantic)    │  │  │
│   │   └─────────┘    └─────────────┘    └───────────┬─────────────┘  │  │
│   │                                                  │                │  │
│   │                         ┌────────────────────────┼───────────┐   │  │
│   │                         ▼                        ▼           │   │  │
│   │   ┌─────────────────────────────┐    ┌───────────────────┐   │   │  │
│   │   │      Upstash Redis          │◀──▶│   Neon PostgreSQL │   │   │  │
│   │   │    (redis-py + hiredis)     │    │   (SQLModel +     │   │   │  │
│   │   │    Cache, 5min TTL          │    │    asyncpg)       │   │   │  │
│   │   └─────────────────────────────┘    └───────────────────┘   │   │  │
│   │                         │                                     │   │  │
│   └─────────────────────────┼─────────────────────────────────────┘   │  │
│                             │                                          │  │
│                             ▼                                          │  │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                         AGENTS                                   │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │  │
│   │  │  Security   │  │   Logic     │  │   Style     │              │  │
│   │  │   Agent     │  │   Agent     │  │   Agent     │              │  │
│   │  └─────────────┘  └─────────────┘  └─────────────┘              │  │
│   └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Tech Stack

| Component         | Library            | Version | Free Tier   |
| ----------------- | ------------------ | ------- | ----------- |
| **ORM**           | SQLModel           | 0.0.14+ | -           |
| **DB Driver**     | asyncpg            | 0.29+   | -           |
| **Database**      | Neon PostgreSQL    | -       | 512MB       |
| **Cache**         | redis-py + hiredis | 5.0+    | -           |
| **Cache Service** | Upstash Redis      | -       | 10K cmd/day |
| **Validation**    | Pydantic v2        | 2.5+    | -           |
| **YAML**          | PyYAML             | 6.0+    | -           |

---

## 📦 Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    # Framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",

    # Database - SQLModel (includes SQLAlchemy + Pydantic)
    "sqlmodel>=0.0.14",
    "asyncpg>=0.29.0",

    # Cache - Redis with C extension for speed
    "redis[hiredis]>=5.0.0",

    # YAML parsing
    "pyyaml>=6.0.1",

    # Already existing...
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
    "structlog>=24.1.0",
]
```

---

## 🔄 Data Flow

### On PR Open/Sync

```
1. Webhook received
2. context_extractor runs
3. ConfigService.get_config(owner, repo) called
4. Check Redis cache (redis-py)
   ├─ HIT: Return cached config
   └─ MISS:
       a. Fetch .reviewer.yaml from GitHub
       b. If exists: Parse YAML → SQLModel validation
       c. If not: Query PostgreSQL via SQLModel
       d. If not: Use hardcoded defaults
       e. Cache result in Redis (5min TTL)
5. Config passed to agents via GraphState
6. Agents apply config (threshold, ignore, instructions)
```

---

## 🗄️ Database Design

### Using SQLModel

```python
# Single model for both DB and validation
class ConfigModel(SQLModel, table=True):
    __tablename__ = "configs"

    id: int | None = Field(default=None, primary_key=True)
    owner: str = Field(index=True)
    repo: str = Field(index=True)
    config_data: dict = Field(sa_column=Column(JSONB))
    created_at: datetime
    updated_at: datetime
```

---

## 🔑 Redis Key Design

```python
# Using redis-py
KEY_PREFIX = "config"
KEY_PATTERN = f"{KEY_PREFIX}:{{owner}}:{{repo}}"

# Example: config:myorg:myrepo
# Value: JSON string of ReviewerConfig
# TTL: 300 seconds (5 minutes)
```

---

## 📁 Module Structure

```
src/core/config/
├── __init__.py              # Exports
├── models.py                # SQLModel models (DB + validation)
├── schemas.py               # Pure Pydantic schemas (API responses)
├── service.py               # ConfigService (main entry)
├── repository.py            # SQLModel CRUD operations
├── cache.py                 # Redis operations
└── loader.py                # GitHub file loading
```

---

## 🎯 Design Principles

1. **SQLModel for everything** - One model for DB + validation
2. **redis-py with hiredis** - Fast C extension
3. **Graceful degradation** - Works without Redis/DB
4. **Async everywhere** - Non-blocking I/O
5. **Type-safe** - Full type hints with SQLModel
