# Configuration System - Setup Guide

Hướng dẫn từng bước để setup Configuration System.

## Prerequisites

- Python 3.11+
- UV package manager
- PostgreSQL database (Neon recommended)
- Redis instance (Upstash recommended)
- GitHub App/Token với repo read access

## Step 1: Environment Variables

Tạo hoặc update file `.env`:

```bash
# ===========================================
# Database (PostgreSQL)
# ===========================================
# Format: postgresql+asyncpg://user:password@host:port/database
# Neon example:
DATABASE_URL=postgresql+asyncpg://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require

# ===========================================
# Cache (Redis)
# ===========================================
# Format: rediss://default:token@host:port
# Upstash example:
UPSTASH_REDIS_URL=rediss://default:your-token@your-endpoint.upstash.io:6379

# ===========================================
# Optional Settings
# ===========================================
# Cache TTL in seconds (default: 300)
CONFIG_CACHE_TTL=300
```

### Lấy Database URL từ Neon

1. Đăng nhập [Neon Console](https://console.neon.tech/)
2. Tạo project mới hoặc chọn project có sẵn
3. Vào **Connection Details**
4. Chọn **Pooled connection** và **asyncpg**
5. Copy connection string

### Lấy Redis URL từ Upstash

1. Đăng nhập [Upstash Console](https://console.upstash.com/)
2. Tạo Redis database mới
3. Vào tab **Details**
4. Copy **Redis URL** (dạng `rediss://...`)

## Step 2: Install Dependencies

```bash
# Sync all dependencies
uv sync

# Verify installation
uv run python -c "import sqlmodel; import asyncpg; import redis; import yaml; print('OK')"
```

## Step 3: Database Migration

### Option A: Sử dụng migration script

```bash
uv run python scripts/migrate_db.py
```

Output expected:

```
Creating database tables...
Tables created successfully!
```

### Option B: Trong code (startup)

```python
# src/app/main.py
from contextlib import asynccontextmanager
from src.core.database import init_db, close_db
from src.core.redis import close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()
    await close_redis()

app = FastAPI(lifespan=lifespan)
```

## Step 4: Verify Setup

### Test Database Connection

```bash
uv run python << 'EOF'
import asyncio
from src.core.database import get_engine
from sqlalchemy import text

async def test():
    engine = await get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(f"Database: OK ({result.scalar()})")

asyncio.run(test())
EOF
```

### Test Redis Connection

```bash
uv run python << 'EOF'
import asyncio
from src.core.redis import get_redis

async def test():
    redis = await get_redis()
    if redis:
        await redis.ping()
        print("Redis: OK")
    else:
        print("Redis: Not configured")

asyncio.run(test())
EOF
```

### Test Config Service

```bash
uv run python << 'EOF'
import asyncio
from src.core.config import create_config_service

async def test():
    service = await create_config_service()
    
    # Get default config (no repo config exists)
    config = await service.get_config("test-owner", "test-repo")
    
    print(f"Language: {config.language}")
    print(f"Profile: {config.reviews.profile}")
    print(f"Threshold: {config.get_threshold()}")
    print(f"Max Comments: {config.get_max_comments()}")
    print("Config Service: OK")

asyncio.run(test())
EOF
```

## Step 5: Create Sample Config

Tạo file `.reviewer.yaml` trong repository muốn review:

```yaml
# Minimal config
language: vi
reviews:
  profile: default

ignore:
  - "**/node_modules/**"
  - "**/*.lock"
```

Hoặc full config:

```yaml
language: vi

reviews:
  profile: strict
  agents:
    - security
    - logic
    - style
  confidence_threshold: 0.6
  max_comments_per_file: 20
  
  path_instructions:
    - path: "src/api/**"
      instructions: "Kiểm tra kỹ authentication và authorization"
    - path: "src/db/**"
      instructions: "Review SQL injection vulnerabilities"
    - path: "**/*.test.ts"
      instructions: "Ensure test isolation and proper mocking"
  
  auto_review:
    enabled: true
    drafts: false
    skip_keywords:
      - "[skip review]"
      - "[wip]"
    base_branches:
      - main
      - develop
    ignore_authors:
      - dependabot[bot]
      - github-actions[bot]

ignore:
  - "**/node_modules/**"
  - "**/dist/**"
  - "**/build/**"
  - "**/*.lock"
  - "**/*.min.js"
  - "**/migrations/**"
  - "**/__pycache__/**"
  - "**/.git/**"

chat:
  enabled: true
  allowed_commands:
    - fix
    - explain
    - tests
    - help
```

## Step 6: Run Tests

```bash
# Run all config tests
uv run pytest tests/core/config/ -v

# Expected output:
# tests/core/config/test_cache.py - 11 passed
# tests/core/config/test_schemas.py - 23 passed
# tests/core/config/test_service.py - 11 passed
# Total: 45 passed
```

## Troubleshooting

### "Connection refused" - Database

```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# Test with psql
psql "$DATABASE_URL" -c "SELECT 1"
```

**Fix**: Đảm bảo URL format đúng và database accessible.

### "Connection refused" - Redis

```bash
# Check UPSTASH_REDIS_URL
echo $UPSTASH_REDIS_URL

# Test with redis-cli
redis-cli -u "$UPSTASH_REDIS_URL" PING
```

**Fix**: Đảm bảo URL có prefix `rediss://` (với SSL) cho Upstash.

### "Table does not exist"

```bash
# Re-run migration
uv run python scripts/migrate_db.py

# Verify table exists
psql "$DATABASE_URL" -c "\dt configs"
```

### "GitHub file not found"

Config sẽ fallback về defaults nếu `.reviewer.yaml` không tồn tại. Đây là hành vi expected.

### "Validation error"

```bash
# Validate YAML locally
uv run python << 'EOF'
import yaml
from src.core.config import ReviewerConfig

with open(".reviewer.yaml") as f:
    data = yaml.safe_load(f)

try:
    config = ReviewerConfig.model_validate(data)
    print("Config is valid!")
    print(config.model_dump_json(indent=2))
except Exception as e:
    print(f"Validation error: {e}")
EOF
```

## Production Checklist

- [ ] DATABASE_URL configured với SSL (`?sslmode=require`)
- [ ] UPSTASH_REDIS_URL sử dụng `rediss://` (SSL)
- [ ] Database tables created via migration
- [ ] GitHub token có read access
- [ ] Config cache TTL phù hợp (default 5 min)
- [ ] Error logging configured
- [ ] Tests passing

## Next Steps

1. Đọc [ARCHITECTURE.md](./ARCHITECTURE.md) để hiểu chi tiết hệ thống
2. Xem [README.md](./README.md) để biết cách sử dụng các features
3. Customize `.reviewer.yaml` cho từng repository
