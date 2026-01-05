# 🏗️ Architecture Decision Record: Configuration System

> **Date**: 2025-12-29  
> **Author**: Solution Architecture  
> **Status**: Proposed

---

## 📋 Context

Cần implement Configuration System cho AI Code Reviewer với yêu cầu:

1. **Đơn giản** - Không cần quá nhiều options như CodeRabbit
2. **Free tier friendly** - Sử dụng dịch vụ miễn phí
3. **Hiệu quả** - Tối ưu cho use case của project

---

## 🎯 Decision: Simplified Configuration

### Những gì KHÔNG cần (bỏ từ CodeRabbit)

| Feature                                 | Lý do bỏ                              |
| --------------------------------------- | ------------------------------------- |
| `poem`, `art`, `fortune`                | Fun features, không essential         |
| `sequence_diagrams`                     | Phức tạp, Phase 2+                    |
| `suggested_labels`, `auto_apply_labels` | Ngoài scope                           |
| `suggested_reviewers`                   | Ngoài scope                           |
| `finishing_touches`                     | Riêng biệt feature                    |
| `pre_merge_checks`                      | Riêng biệt feature                    |
| `tools.*` (linters)                     | Chúng ta dùng LLM, không dùng linters |
| `knowledge_base`                        | Riêng biệt feature                    |
| `integrations` (jira, linear)           | Riêng biệt feature                    |

### Những gì CẦN (MVP)

| Feature                         | Lý do              |
| ------------------------------- | ------------------ |
| `language`                      | Response language  |
| `reviews.profile`               | Control strictness |
| `reviews.agents`                | Chọn agents chạy   |
| `reviews.confidence_threshold`  | Filter noise       |
| `reviews.max_comments_per_file` | Limit output       |
| `reviews.path_instructions`     | **Core feature**   |
| `reviews.auto_review`           | Control triggers   |
| `ignore.paths`                  | Skip files         |
| `chat.enabled`                  | Control commands   |

---

## 📐 Simplified Schema (MVP)

```yaml
# .reviewer.yaml - Minimized Version

# Response language
language: "vi" # en | vi | ja | etc.

# Review settings
reviews:
  # Profile: chill (lenient) | strict (aggressive)
  profile: "chill"

  # Which agents to run
  agents:
    - security
    - logic
    - style

  # Minimum confidence to report (0.0 - 1.0)
  confidence_threshold: 0.7

  # Max comments per file
  max_comments_per_file: 10

  # Per-path custom instructions
  path_instructions:
    - path: "src/api/**/*.py"
      instructions: "Check authentication"

  # Auto-review settings
  auto_review:
    enabled: true
    drafts: false
    skip_keywords: # Skip PRs với keywords trong title
      - "[WIP]"
      - "[SKIP]"

# Files to ignore
ignore:
  - "**/__pycache__/**"
  - "**/migrations/**"
  - "*.lock"

# Chat commands
chat:
  enabled: true
```

### Tổng cộng: **8 fields** (vs ~50+ của CodeRabbit)

---

## 🏛️ Technology Stack & Architecture

### Option 1: File-Only (Recommended for MVP) ⭐

```
┌─────────────────────────────────────────────────────────────┐
│                    GITHUB REPOSITORY                         │
│  ┌─────────────────┐                                        │
│  │ .reviewer.yaml  │  ← Config stored in repo               │
│  └────────┬────────┘                                        │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI REVIEWER SERVICE                       │
│  ┌──────────────┐    ┌──────────────┐                       │
│  │ Config       │───▶│ In-Memory    │                       │
│  │ Loader       │    │ Cache (5min) │                       │
│  └──────────────┘    └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**

- ✅ Zero infrastructure cost
- ✅ Config versioned with code
- ✅ Simple implementation
- ✅ No database needed

**Cons:**

- ❌ No central config across repos
- ❌ Must commit to change config

**Tech Stack:**

- **Storage**: GitHub file (via API)
- **Cache**: Python dict in memory
- **Parsing**: PyYAML + Pydantic

---

### Option 2: With Database (For Future Learnings)

```
┌─────────────────────────────────────────────────────────────┐
│                    GITHUB REPOSITORY                         │
│  └─ .reviewer.yaml (optional override)                      │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI REVIEWER SERVICE                       │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Config       │───▶│ Redis Cache  │◀──▶│ PostgreSQL    │  │
│  │ Service      │    │ (5min TTL)   │    │ (persistent)  │  │
│  └──────────────┘    └──────────────┘    └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Free Tier Options:**

| Service           | Free Tier            | Notes                  |
| ----------------- | -------------------- | ---------------------- |
| **Supabase**      | 500MB DB, 2 projects | PostgreSQL, auth, APIs |
| **PlanetScale**   | 5GB, 1B reads/month  | MySQL-compatible       |
| **Neon**          | 512MB, 3 projects    | PostgreSQL, serverless |
| **Upstash Redis** | 10K commands/day     | Redis, serverless      |
| **Railway**       | $5 credit/month      | Any DB, easy setup     |

---

## 🎯 Recommendation: Phased Approach

### Phase 1: File-Only (Now) ⭐

**Do this first:**

- Config từ `.reviewer.yaml` trong repo
- In-memory cache (5 phút TTL)
- Fallback to defaults

**Cost: $0**

```python
# Simple implementation
class ConfigLoader:
    _cache: dict[str, tuple[Config, float]] = {}

    async def load(self, owner, repo) -> Config:
        # 1. Check cache
        # 2. Fetch from GitHub API
        # 3. Parse YAML
        # 4. Cache and return
```

### Phase 2: Add Database (When Needed)

**Khi nào cần:**

- Khi implement Learnings/Memory
- Khi cần central config
- Khi cần config history

**Recommended Stack (All Free Tier):**

| Component      | Service           | Why                            |
| -------------- | ----------------- | ------------------------------ |
| Database       | **Supabase**      | PostgreSQL, generous free tier |
| Cache          | **Upstash Redis** | Serverless, 10K/day free       |
| Config History | Supabase          | Same DB                        |

---

## 📦 Minimal Implementation

### Pydantic Models (Simplified)

```python
# src/core/config/models.py
from pydantic import BaseModel, Field

class PathInstruction(BaseModel):
    path: str
    instructions: str

class AutoReview(BaseModel):
    enabled: bool = True
    drafts: bool = False
    skip_keywords: list[str] = []

class Reviews(BaseModel):
    profile: str = "chill"  # chill | strict
    agents: list[str] = ["security", "logic", "style"]
    confidence_threshold: float = 0.7
    max_comments_per_file: int = 10
    path_instructions: list[PathInstruction] = []
    auto_review: AutoReview = AutoReview()

class Chat(BaseModel):
    enabled: bool = True

class ReviewerConfig(BaseModel):
    """Minimal config schema."""
    language: str = "en"
    reviews: Reviews = Reviews()
    ignore: list[str] = []
    chat: Chat = Chat()
```

### Config Loader (File-Only)

```python
# src/core/config/loader.py
import time
import yaml
from .models import ReviewerConfig

class ConfigLoader:
    """Load config from repository."""

    CACHE_TTL = 300  # 5 minutes
    _cache: dict[str, tuple[ReviewerConfig, float]] = {}

    async def load(self, github, owner: str, repo: str) -> ReviewerConfig:
        cache_key = f"{owner}/{repo}"

        # Check cache
        if cache_key in self._cache:
            config, ts = self._cache[cache_key]
            if time.time() - ts < self.CACHE_TTL:
                return config

        # Load from GitHub
        try:
            content = await github.get_file_raw(owner, repo, ".reviewer.yaml")
            data = yaml.safe_load(content) if content else {}
            config = ReviewerConfig(**data)
        except Exception:
            config = ReviewerConfig()  # Defaults

        # Cache
        self._cache[cache_key] = (config, time.time())
        return config

    def matches(self, path: str, pattern: str) -> bool:
        """Simple glob matching."""
        import fnmatch
        if "**" in pattern:
            # Convert ** to regex
            import re
            regex = pattern.replace("**", ".*").replace("*", "[^/]*")
            return bool(re.match(regex, path))
        return fnmatch.fnmatch(path, pattern)
```

---

## 📊 Comparison

| Aspect        | CodeRabbit | Our MVP   |
| ------------- | ---------- | --------- |
| Config fields | ~50+       | 8         |
| Storage       | DB + YAML  | YAML only |
| Cache         | Redis      | In-memory |
| Cost          | Paid       | $0        |
| Setup time    | -          | ~1 day    |

---

## ✅ Implementation Checklist (Simplified)

### Day 1: Core

- [ ] Create `src/core/config/models.py` (simplified)
- [ ] Create `src/core/config/loader.py`
- [ ] Add `get_file_raw()` to GitHubService
- [ ] Unit tests

### Day 2: Integration

- [ ] Load config in `context_extractor.py`
- [ ] Apply `ignore` patterns
- [ ] Apply `path_instructions` to prompts
- [ ] Apply `confidence_threshold`

### Day 3: Polish

- [ ] Create example `.reviewer.yaml`
- [ ] Update docs
- [ ] Integration test

---

## 🚀 Quick Start After Implementation

```yaml
# .reviewer.yaml
language: "vi"
reviews:
  profile: "chill"
  path_instructions:
    - path: "tests/**"
      instructions: "Light review"
ignore:
  - "**/migrations/**"
```

Commit file này và reviewer sẽ tự động dùng config!
