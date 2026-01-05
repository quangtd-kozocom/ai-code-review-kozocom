# 09 - Professional Libraries & Patterns

> Sử dụng các thư viện nổi tiếng để code chuyên nghiệp hơn.

---

## 📦 Recommended Tech Stack

### So Sánh Options

| Component      | Basic             | Professional                      | Recommendation         |
| -------------- | ----------------- | --------------------------------- | ---------------------- |
| **ORM/DB**     | `asyncpg` raw     | **SQLAlchemy 2.0** / **SQLModel** | SQLModel ⭐            |
| **Redis**      | `redis-py` raw    | **Redis-OM** / **aioredis**       | Redis-OM ⭐            |
| **Validation** | Pydantic only     | **Pydantic v2**                   | Already using ✅       |
| **DI**         | Manual            | **dependency-injector**           | dependency-injector ⭐ |
| **Settings**   | pydantic-settings | **pydantic-settings**             | Already using ✅       |

---

## 🏆 Option 1: SQLModel (Best for Pydantic users)

**SQLModel** = SQLAlchemy + Pydantic by the same author (Sebastián Ramírez - FastAPI creator)

### Why SQLModel?

- ✅ Same models for DB and API
- ✅ Full Pydantic validation
- ✅ Async support
- ✅ Type hints everywhere
- ✅ FastAPI native integration

### Installation

```bash
pip install sqlmodel aiosqlite asyncpg
# or
poetry add sqlmodel asyncpg
```

### Example Usage

```python
# src/core/config/models.py
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class ConfigBase(SQLModel):
    """Base config model (shared fields)."""
    language: str = Field(default="en")
    reviews_profile: str = Field(default="default")
    reviews_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    ignore_patterns: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    path_instructions: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))


class Config(ConfigBase, table=True):
    """Database model."""
    __tablename__ = "configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner: str = Field(index=True)
    repo: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Unique constraint
        __table_args__ = (
            UniqueConstraint("owner", "repo", name="unique_owner_repo"),
        )


class ConfigCreate(ConfigBase):
    """Create request model."""
    owner: str
    repo: str


class ConfigRead(ConfigBase):
    """Response model."""
    id: int
    owner: str
    repo: str
    created_at: datetime
```

### Repository with SQLModel

```python
# src/core/config/repository.py
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import Config, ConfigCreate


class ConfigRepository:
    """Repository for config CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, owner: str, repo: str) -> Config | None:
        """Get config by owner/repo."""
        statement = select(Config).where(
            Config.owner == owner,
            Config.repo == repo
        )
        result = await self.session.exec(statement)
        return result.first()

    async def create(self, config: ConfigCreate) -> Config:
        """Create new config."""
        db_config = Config.model_validate(config)
        self.session.add(db_config)
        await self.session.commit()
        await self.session.refresh(db_config)
        return db_config

    async def upsert(self, owner: str, repo: str, data: dict) -> Config:
        """Insert or update config."""
        existing = await self.get(owner, repo)

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
        else:
            existing = Config(owner=owner, repo=repo, **data)
            self.session.add(existing)

        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def delete(self, owner: str, repo: str) -> bool:
        """Delete config."""
        config = await self.get(owner, repo)
        if config:
            await self.session.delete(config)
            await self.session.commit()
            return True
        return False
```

### Database Setup with SQLModel

```python
# src/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ..app.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session
```

---

## 🔴 Option 2: Redis-OM (Object Mapping for Redis)

**Redis-OM** = ORM-like experience for Redis by Redis Labs

### Why Redis-OM?

- ✅ Pydantic models for Redis
- ✅ Automatic JSON serialization
- ✅ Full-text search support
- ✅ Async native
- ✅ Type-safe queries

### Installation

```bash
pip install redis-om
# or
poetry add redis-om
```

### Example Usage

```python
# src/core/config/cache.py
from datetime import datetime
from typing import Optional
from redis_om import HashModel, Field, get_redis_connection

from ..app.config import get_settings


# Connect to Upstash
redis = get_redis_connection(
    url=get_settings().UPSTASH_REDIS_URL,
    decode_responses=True
)


class CachedConfig(HashModel):
    """Cached config model in Redis."""

    owner: str = Field(index=True)
    repo: str = Field(index=True)
    language: str = Field(default="en")
    profile: str = Field(default="default")
    threshold: float = Field(default=0.7)
    ignore_patterns: str = Field(default="[]")  # JSON string
    path_instructions: str = Field(default="[]")  # JSON string
    cached_at: datetime = Field(default_factory=datetime.utcnow)

    class Meta:
        database = redis
        global_key_prefix = "reviewer"
        model_key_prefix = "config"


class ConfigCache:
    """Cache service using Redis-OM."""

    TTL_SECONDS = 300  # 5 minutes

    async def get(self, owner: str, repo: str) -> Optional[dict]:
        """Get cached config."""
        try:
            # Find by owner and repo
            results = CachedConfig.find(
                (CachedConfig.owner == owner) &
                (CachedConfig.repo == repo)
            ).all()

            if results:
                config = results[0]
                # Check TTL
                age = (datetime.utcnow() - config.cached_at).total_seconds()
                if age < self.TTL_SECONDS:
                    return self._to_dict(config)
                # Expired, delete
                await CachedConfig.delete(config.pk)
            return None
        except Exception:
            return None

    async def set(self, owner: str, repo: str, config: dict) -> None:
        """Cache config."""
        try:
            # Delete existing
            existing = CachedConfig.find(
                (CachedConfig.owner == owner) &
                (CachedConfig.repo == repo)
            ).all()
            for e in existing:
                await CachedConfig.delete(e.pk)

            # Create new
            cached = CachedConfig(
                owner=owner,
                repo=repo,
                language=config.get("language", "en"),
                profile=config.get("reviews", {}).get("profile", "default"),
                threshold=config.get("reviews", {}).get("confidence_threshold", 0.7),
                ignore_patterns=json.dumps(config.get("ignore", [])),
                path_instructions=json.dumps(
                    config.get("reviews", {}).get("path_instructions", [])
                ),
            )
            await cached.save()
            await cached.expire(self.TTL_SECONDS)
        except Exception:
            pass

    def _to_dict(self, config: CachedConfig) -> dict:
        """Convert to config dict."""
        return {
            "language": config.language,
            "reviews": {
                "profile": config.profile,
                "confidence_threshold": config.threshold,
                "path_instructions": json.loads(config.path_instructions),
            },
            "ignore": json.loads(config.ignore_patterns),
        }
```

---

## 💉 Option 3: Dependency Injection

**dependency-injector** = Professional DI container

### Why Dependency Injection?

- ✅ Testable code (easy mocking)
- ✅ Clean separation of concerns
- ✅ Configuration management
- ✅ Industry standard pattern

### Installation

```bash
pip install dependency-injector
# or
poetry add dependency-injector
```

### Container Setup

```python
# src/core/containers.py
from dependency_injector import containers, providers

from .config.service import ConfigService
from .config.repository import ConfigRepository
from .config.cache import ConfigCache
from .database import async_session
from ..app.services.github import GitHubService


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    # Configuration
    config = providers.Configuration()

    # Database session
    db_session = providers.Resource(
        async_session
    )

    # Redis connection
    redis = providers.Singleton(
        get_redis_connection,
        url=config.upstash_redis_url,
    )

    # Repositories
    config_repository = providers.Factory(
        ConfigRepository,
        session=db_session,
    )

    # Cache
    config_cache = providers.Singleton(
        ConfigCache,
        redis=redis,
    )

    # Services
    config_service = providers.Factory(
        ConfigService,
        repository=config_repository,
        cache=config_cache,
    )

    # GitHub service (per installation)
    github_service = providers.Factory(
        GitHubService,
    )
```

### Usage in FastAPI

```python
# src/app/main.py
from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from ..core.containers import Container
from ..core.config.service import ConfigService


container = Container()
container.config.from_dict({
    "database_url": settings.DATABASE_URL,
    "upstash_redis_url": settings.UPSTASH_REDIS_URL,
})


@app.get("/config/{owner}/{repo}")
@inject
async def get_config(
    owner: str,
    repo: str,
    config_service: ConfigService = Depends(Provide[Container.config_service]),
):
    return await config_service.get_config(owner, repo)
```

---

## 📊 Final Recommendation

### For This Project

| Component    | Library               | Why                                     |
| ------------ | --------------------- | --------------------------------------- |
| **Database** | **SQLModel**          | Pydantic native, async, FastAPI creator |
| **Cache**    | **redis-py** + custom | Redis-OM overkill for simple caching    |
| **DI**       | **Optional**          | Keep simple for now, add later          |

### Updated Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    # Framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",

    # Database - SQLModel (includes SQLAlchemy)
    "sqlmodel>=0.0.14",
    "asyncpg>=0.29.0",

    # Redis
    "redis[hiredis]>=5.0.0",

    # Validation & Config
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0.1",

    # LLM
    "langchain>=0.1.0",
    "langchain-openai>=0.0.5",

    # HTTP
    "httpx>=0.26.0",

    # Task Queue
    "celery[redis]>=5.3.0",

    # Logging
    "structlog>=24.1.0",
]
```

---

## 🔄 Migration Path

### Phase 1 (Now): Simple

- `asyncpg` raw queries
- `redis-py` simple cache
- Works, fast to implement

### Phase 2 (Later): Professional

- Migrate to SQLModel
- Add proper migrations (Alembic)
- Add dependency injection
- Better testability

---

## 📋 Code Quality Patterns

### 1. Repository Pattern

```python
# Clean separation: Repository handles data access only
class ConfigRepository:
    async def get(self, owner, repo): ...
    async def create(self, config): ...
    async def update(self, owner, repo, data): ...
    async def delete(self, owner, repo): ...
```

### 2. Service Pattern

```python
# Service handles business logic, uses repositories
class ConfigService:
    def __init__(self, repository, cache, loader):
        self.repository = repository
        self.cache = cache
        self.loader = loader

    async def get_config(self, owner, repo):
        # Business logic: cache → github → db → defaults
        ...
```

### 3. Factory Pattern

```python
# Factory creates complex objects
class ConfigServiceFactory:
    @staticmethod
    async def create(github: GitHubService) -> ConfigService:
        session = await get_session()
        redis = await get_redis()
        return ConfigService(
            repository=ConfigRepository(session),
            cache=ConfigCache(redis),
            loader=ConfigLoader(github),
        )
```

### 4. Strategy Pattern (for profiles)

```python
# Different strategies for different profiles
class ReviewStrategy(ABC):
    @abstractmethod
    def get_threshold(self) -> float: ...
    @abstractmethod
    def get_max_comments(self) -> int: ...

class ChillStrategy(ReviewStrategy):
    def get_threshold(self) -> float:
        return 0.85
    def get_max_comments(self) -> int:
        return 5

class StrictStrategy(ReviewStrategy):
    def get_threshold(self) -> float:
        return 0.6
    def get_max_comments(self) -> int:
        return 20
```

---

## ✅ Summary

| Approach                       | Complexity | Professionalism | Time   |
| ------------------------------ | ---------- | --------------- | ------ |
| **Basic** (asyncpg + redis-py) | Low        | Medium          | 2 days |
| **SQLModel + redis-py**        | Medium     | High            | 3 days |
| **Full (SQLModel + DI)**       | High       | Enterprise      | 5 days |

**Recommendation**: Start with **SQLModel + redis-py** for the best balance of professionalism and simplicity.
