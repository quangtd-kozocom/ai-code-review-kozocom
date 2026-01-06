# Configuration System

Hệ thống Configuration cho phép mỗi repository tùy chỉnh hành vi của AI Code Reviewer thông qua file `.reviewer.yaml`.

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Kiến trúc](#kiến-trúc)
3. [Cài đặt](#cài-đặt)
4. [Sử dụng](#sử-dụng)
5. [Testing](#testing)
6. [API Reference](#api-reference)

## Tổng quan

### Tính năng chính

- **Profile-based Review**: 3 mức độ review (chill/default/strict)
- **Path Instructions**: Hướng dẫn riêng cho từng đường dẫn file
- **Auto Review**: Tự động quyết định review PR dựa trên điều kiện
- **Ignore Patterns**: Bỏ qua file theo glob patterns
- **Multi-language**: Hỗ trợ đa ngôn ngữ (en/vi/ja)
- **Agent Control**: Bật/tắt từng agent (security/logic/style)

### Config Resolution Order

```
┌─────────────────┐
│  Redis Cache    │ ← Ưu tiên cao nhất (TTL 5 phút)
└────────┬────────┘
         │ miss
         ▼
┌─────────────────┐
│  GitHub YAML    │ ← File .reviewer.yaml trong repo
└────────┬────────┘
         │ not found
         ▼
┌─────────────────┐
│  PostgreSQL     │ ← Database storage
└────────┬────────┘
         │ not found
         ▼
┌─────────────────┐
│  Defaults       │ ← Giá trị mặc định
└─────────────────┘
```

## Kiến trúc

### File Structure

```
src/core/config/
├── __init__.py          # Module exports
├── schemas.py           # Pydantic validation models
├── models.py            # SQLModel cho database
├── cache.py             # Redis cache wrapper
├── repository.py        # Database CRUD operations
├── loader.py            # GitHub YAML loader
└── service.py           # Main orchestration service

src/core/
├── database.py          # PostgreSQL connection
└── redis.py             # Redis connection
```

### Components

| Component          | Responsibility                                  |
| ------------------ | ----------------------------------------------- |
| `ReviewerConfig`   | Pydantic model với validation và helper methods |
| `ConfigCache`      | Redis caching với TTL                           |
| `ConfigRepository` | CRUD operations cho PostgreSQL                  |
| `ConfigLoader`     | Load và parse .reviewer.yaml từ GitHub          |
| `ConfigService`    | Orchestrate tất cả components                   |

## Cài đặt

### 1. Environment Variables

Thêm vào `.env`:

```bash
# PostgreSQL (Neon)
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Redis (for Celery and Cache - Upstash recommended)
REDIS_URL=rediss://default:token@host:6379

# Cache TTL (optional, default 300 seconds)
CONFIG_CACHE_TTL=300
```

### 2. Dependencies

Dependencies đã được thêm vào `pyproject.toml`:

```toml
dependencies = [
    "sqlmodel>=0.0.22",
    "asyncpg>=0.30.0",
    "redis[hiredis]>=5.2.0",
    "pyyaml>=6.0.2",
    # ... other deps
]
```

Sync dependencies:

```bash
uv sync
```

### 3. Database Migration

Chạy migration script để tạo bảng:

```bash
uv run python scripts/migrate_db.py
```

Hoặc trong code:

```python
from src.core.database import init_db

await init_db()
```

## Sử dụng

### Tạo file .reviewer.yaml

Tạo file `.reviewer.yaml` ở root của repository:

```yaml
# Ngôn ngữ output (en/vi/ja)
language: vi

# Review settings
reviews:
  # Profile: chill (ít nghiêm ngặt), default, strict (rất nghiêm ngặt)
  profile: default

  # Agents để chạy
  agents:
    - security
    - logic
    - style

  # Confidence threshold (0.0 - 1.0)
  # Chỉ report issues với confidence >= threshold
  confidence_threshold: 0.7

  # Số comments tối đa mỗi file
  max_comments_per_file: 10

  # Hướng dẫn theo path
  path_instructions:
    - path: "src/api/**"
      instructions: "Kiểm tra authentication và rate limiting"
    - path: "**/*.test.ts"
      instructions: "Đảm bảo test coverage > 80%"

  # Auto review settings
  auto_review:
    enabled: true
    drafts: false # Không review draft PRs
    skip_keywords:
      - "[skip review]"
      - "[no review]"
    base_branches:
      - main
      - develop
    ignore_authors:
      - dependabot[bot]
      - renovate[bot]

# Files/folders to ignore
ignore:
  - "**/*.lock"
  - "**/node_modules/**"
  - "**/dist/**"
  - "**/*.min.js"

# Chat settings
chat:
  enabled: true
  allowed_commands:
    - fix
    - explain
    - tests
    - help
```

### Profile Behaviors

| Profile   | Threshold | Max Comments | Mô tả                    |
| --------- | --------- | ------------ | ------------------------ |
| `chill`   | 0.85      | 5            | Chỉ báo lỗi nghiêm trọng |
| `default` | 0.70      | 10           | Cân bằng                 |
| `strict`  | 0.60      | 20           | Review kỹ lưỡng          |

### Sử dụng trong Code

```python
from src.core.config import ConfigService, create_config_service

# Tạo service
config_service = await create_config_service()

# Lấy config cho repository
config = await config_service.get_config(
    owner="organization",
    repo="repository",
    ref="main"  # branch/tag
)

# Sử dụng config
if config.should_ignore("node_modules/package.json"):
    print("Skip file")

threshold = config.get_threshold()
max_comments = config.get_max_comments()

instructions = config.get_path_instructions("src/api/users.py")
# ["Kiểm tra authentication và rate limiting"]

if config.should_auto_review(
    title="feat: add login",
    author="developer",
    base_branch="main",
    is_draft=False
):
    print("Should review this PR")

if config.is_agent_enabled("security"):
    print("Run security agent")
```

### Glob Patterns

Hệ thống hỗ trợ glob patterns:

| Pattern        | Matches                           | Not Matches       |
| -------------- | --------------------------------- | ----------------- |
| `*.py`         | `test.py`                         | `src/test.py`     |
| `src/*.py`     | `src/main.py`                     | `src/sub/main.py` |
| `src/**`       | `src/a/b/c.py`                    | `test.py`         |
| `**/test/**`   | `test/unit.py`, `src/test/e2e.py` | `testing/a.py`    |
| `**/*.test.ts` | `a.test.ts`, `src/b.test.ts`      | `test.ts`         |

## Testing

### Chạy Tests

```bash
# Chạy tất cả config tests
uv run pytest tests/core/config/ -v

# Chạy test cụ thể
uv run pytest tests/core/config/test_schemas.py -v
uv run pytest tests/core/config/test_service.py -v

# Chạy với coverage
uv run pytest tests/core/config/ --cov=src/core/config
```

### Test Files

| File              | Coverage                                         |
| ----------------- | ------------------------------------------------ |
| `test_schemas.py` | Validation, glob patterns, profiles, auto-review |
| `test_cache.py`   | Redis operations, error handling                 |
| `test_service.py` | Config resolution, fallbacks                     |

### Manual Testing

```python
# Test glob pattern matching
from src.core.config import ReviewerConfig

config = ReviewerConfig(ignore=["**/migrations/**", "*.lock"])

assert config.should_ignore("src/migrations/001.py") == True
assert config.should_ignore("migrations/init.py") == True
assert config.should_ignore("package-lock.json") == False  # *.lock không match
assert config.should_ignore("yarn.lock") == True
```

## API Reference

### ReviewerConfig

```python
class ReviewerConfig(BaseModel):
    language: str = "en"
    reviews: ReviewsConfig
    ignore: list[str] = []
    chat: ChatConfig

    # Methods
    def get_threshold() -> float
    def get_max_comments() -> int
    def should_ignore(file_path: str) -> bool
    def get_path_instructions(file_path: str) -> list[str]
    def should_auto_review(title, author, base_branch, is_draft) -> bool
    def is_agent_enabled(agent: str) -> bool
```

### ConfigService

```python
class ConfigService:
    async def get_config(owner: str, repo: str, ref: str = "main") -> ReviewerConfig
    async def save_config(owner: str, repo: str, config: ReviewerConfig) -> None
    async def delete_config(owner: str, repo: str) -> None
    async def invalidate_cache(owner: str, repo: str) -> None
```

### Factory Function

```python
async def create_config_service(
    github_token: str | None = None,
    cache_ttl: int | None = None,
) -> ConfigService
```

## Troubleshooting

### Cache không hoạt động

```python
# Kiểm tra Redis connection
from src.core.redis import get_redis

redis = await get_redis()
await redis.ping()  # Should return True
```

### Config không load từ GitHub

```python
# Kiểm tra file tồn tại
from src.app.services.github import GitHubService

github = GitHubService(token="...")
content = await github.get_file_raw(owner, repo, ".reviewer.yaml", ref)
print(content)
```

### Database errors

```python
# Kiểm tra connection
from src.core.database import get_engine

engine = await get_engine()
async with engine.connect() as conn:
    result = await conn.execute(text("SELECT 1"))
    print(result.scalar())
```

## Xem thêm

- [Architecture Overview](../autofix/ARCHITECTURE.md)
- [Database Schema](../../ideas/configuration-system/)
