# Configuration System - Kiến trúc Chi tiết

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ConfigService                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐               │
│  │ ConfigCache │  │ ConfigLoader │  │ConfigRepository│               │
│  │   (Redis)   │  │  (GitHub)    │  │  (PostgreSQL) │               │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘               │
└─────────┼────────────────┼──────────────────┼───────────────────────┘
          │                │                  │
          ▼                ▼                  ▼
    ┌──────────┐    ┌────────────┐    ┌─────────────┐
    │  Upstash │    │   GitHub   │    │    Neon     │
    │  Redis   │    │    API     │    │ PostgreSQL  │
    └──────────┘    └────────────┘    └─────────────┘
```

## Data Flow

### Get Config Flow

```
Client Request
      │
      ▼
┌─────────────────────────────────────────┐
│           ConfigService.get_config()     │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  1. Check Redis Cache                    │
│     key: "config:{owner}:{repo}"         │
│     TTL: 300 seconds                     │
└─────────────────────────────────────────┘
      │
      ├─── HIT ──► Return cached config
      │
      ▼ MISS
┌─────────────────────────────────────────┐
│  2. Load from GitHub                     │
│     GET /{owner}/{repo}/.reviewer.yaml   │
│     Parse YAML → Validate → Cache        │
└─────────────────────────────────────────┘
      │
      ├─── SUCCESS ──► Return & cache
      │
      ▼ NOT FOUND / ERROR
┌─────────────────────────────────────────┐
│  3. Load from Database                   │
│     SELECT FROM configs                  │
│     WHERE owner=? AND repo=?             │
└─────────────────────────────────────────┘
      │
      ├─── FOUND ──► Return & cache
      │
      ▼ NOT FOUND
┌─────────────────────────────────────────┐
│  4. Return Default Config                │
│     ReviewerConfig()                     │
└─────────────────────────────────────────┘
```

## Schemas

### ReviewerConfig (Pydantic)

```python
class ReviewerConfig(BaseModel):
    """Main configuration model."""
    
    model_config = ConfigDict(
        extra="ignore",      # Ignore unknown fields
        frozen=False,        # Mutable
        validate_default=True,
    )
    
    language: str = "en"
    reviews: ReviewsConfig = Field(default_factory=ReviewsConfig)
    ignore: list[str] = Field(default_factory=list)
    chat: ChatConfig = Field(default_factory=ChatConfig)
```

### ReviewsConfig

```python
class ReviewsConfig(BaseModel):
    """Review behavior configuration."""
    
    profile: ReviewProfile = ReviewProfile.DEFAULT
    agents: list[str] = ["security", "logic", "style"]
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_comments_per_file: int = Field(default=10, ge=1, le=50)
    path_instructions: list[PathInstruction] = []
    auto_review: AutoReviewConfig = Field(default_factory=AutoReviewConfig)
```

### ConfigModel (SQLModel)

```python
class ConfigModel(SQLModel, table=True):
    """Database model for config storage."""
    
    __tablename__ = "configs"
    
    id: int | None = Field(default=None, primary_key=True)
    owner: str = Field(index=True)
    repo: str = Field(index=True)
    config_data: dict = Field(sa_column=Column(JSONB))
    created_at: datetime
    updated_at: datetime
```

## Glob Pattern Matching

### Algorithm

```python
@staticmethod
def _glob_to_regex(pattern: str) -> str:
    """
    Convert glob to regex:
    - **/ at start → (.*/)?  (optional prefix)
    - /** at end   → (/.*)?  (optional suffix)
    - **           → .*      (any path)
    - *            → [^/]*   (any except /)
    - ?            → [^/]    (single char except /)
    """
```

### Examples

| Glob Pattern | Regex | Matches |
|--------------|-------|---------|
| `*.py` | `^[^/]*\.py$` | `test.py` |
| `src/**` | `^src(/.*)?$` | `src/a/b.py` |
| `**/test/**` | `^(.*/)?test(/.*)?$` | `test/a.py`, `src/test/b.py` |
| `**/*.py` | `^(.*/)?[^/]*\.py$` | `a.py`, `src/a.py` |

## Caching Strategy

### Redis Key Format

```
config:{owner}:{repo}
```

### TTL

- Default: 300 seconds (5 minutes)
- Configurable via `CONFIG_CACHE_TTL` env var

### Cache Invalidation

```python
# Manual invalidation
await config_service.invalidate_cache(owner, repo)

# Auto-invalidation on save/delete
await config_service.save_config(owner, repo, config)  # invalidates cache
await config_service.delete_config(owner, repo)        # invalidates cache
```

### Error Handling

Cache errors are logged but don't fail the request:

```python
async def get(self, key: str) -> ReviewerConfig | None:
    try:
        data = await self._redis.get(key)
        return ReviewerConfig.model_validate_json(data) if data else None
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
        return None  # Fallback to next source
```

## Database Schema

### Table: configs

```sql
CREATE TABLE configs (
    id SERIAL PRIMARY KEY,
    owner VARCHAR NOT NULL,
    repo VARCHAR NOT NULL,
    config_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(owner, repo)
);

CREATE INDEX idx_configs_owner_repo ON configs(owner, repo);
```

### JSONB Storage

Config được lưu dạng JSONB để:
- Flexible schema evolution
- Query specific fields nếu cần
- No migration needed for new fields

## Integration với Agents

### GraphState Update

```python
class GraphState(TypedDict):
    # ... existing fields
    repo_config: ReviewerConfig  # NEW: Config cho repository
```

### Agent Usage

```python
# In agent node
async def analyze(state: GraphState) -> GraphState:
    config = state["repo_config"]
    
    # Check if agent enabled
    if not config.is_agent_enabled("security"):
        return state
    
    # Get threshold for this profile
    threshold = config.get_threshold()
    
    # Get path-specific instructions
    for file in state["files"]:
        instructions = config.get_path_instructions(file.path)
        # Include instructions in prompt
    
    # Filter by confidence
    issues = [i for i in raw_issues if i.confidence >= threshold]
    
    # Limit comments
    issues = issues[:config.get_max_comments()]
```

## Error Handling

### Graceful Degradation

```
┌─────────────────┐
│  Redis Error    │──► Log warning, continue to GitHub
└─────────────────┘

┌─────────────────┐
│  GitHub Error   │──► Log warning, continue to Database
└─────────────────┘

┌─────────────────┐
│  Database Error │──► Log warning, return defaults
└─────────────────┘

┌─────────────────┐
│  All Errors     │──► Return ReviewerConfig() with safe defaults
└─────────────────┘
```

### Validation Errors

Invalid YAML hoặc config sẽ log error và fallback:

```python
try:
    config = ReviewerConfig.model_validate(yaml_data)
except ValidationError as e:
    logger.error(f"Invalid config: {e}")
    return ReviewerConfig()  # Use defaults
```

## Performance Considerations

### Caching

- 5 minute TTL balances freshness vs performance
- Redis hiredis extension for faster parsing
- JSON serialization for compact storage

### Database

- Async PostgreSQL driver (asyncpg)
- Connection pooling via SQLAlchemy
- Indexed queries on (owner, repo)

### GitHub API

- Single file fetch, not full repo
- Raw content endpoint (no JSON parsing)
- Cached result reduces API calls
