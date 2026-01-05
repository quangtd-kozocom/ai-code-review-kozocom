# 🛠️ Implementation Plan

> Step-by-step kế hoạch implement Configuration System.

---

## 📁 Files Cần Tạo/Sửa

```
src/
├── core/
│   └── config/                    # NEW FOLDER
│       ├── __init__.py            # NEW
│       ├── models.py              # NEW - Pydantic models
│       └── loader.py              # NEW - Config loader
├── agents/
│   ├── state.py                   # MODIFY - Add repo_config
│   └── nodes/
│       ├── context_extractor.py   # MODIFY - Load config
│       ├── security_agent.py      # MODIFY - Use config
│       ├── logic_agent.py         # MODIFY - Use config
│       └── style_agent.py         # MODIFY - Use config
└── app/
    └── services/
        └── github.py              # MODIFY - Add get_file_content_raw
```

---

## 📅 Day 1: Core Models

### Task 1.1: Create Pydantic Models

**File:** `src/core/config/models.py`

```python
from enum import StrEnum
from pydantic import BaseModel, Field

class ReviewProfile(StrEnum):
    CHILL = "chill"
    DEFAULT = "default"
    STRICT = "strict"

class PathInstruction(BaseModel):
    path: str
    instructions: str

class AutoReviewConfig(BaseModel):
    enabled: bool = True
    drafts: bool = False
    ignore_title_keywords: list[str] = Field(default_factory=list)
    base_branches: list[str] = Field(default_factory=list)
    ignore_usernames: list[str] = Field(default_factory=list)

class ReviewsConfig(BaseModel):
    profile: ReviewProfile = ReviewProfile.DEFAULT
    agents: list[str] = Field(default=["security", "logic", "style"])
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_comments_per_file: int = Field(default=10, ge=1)
    path_instructions: list[PathInstruction] = Field(default_factory=list)
    auto_review: AutoReviewConfig = Field(default_factory=AutoReviewConfig)

class ChatConfig(BaseModel):
    enabled: bool = True
    allowed_commands: list[str] = Field(
        default=["fix", "explain", "tests", "help"]
    )

class IgnoreConfig(BaseModel):
    paths: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)

class ReviewerConfig(BaseModel):
    """Root configuration model."""
    language: str = "en"
    reviews: ReviewsConfig = Field(default_factory=ReviewsConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    ignore: IgnoreConfig = Field(default_factory=IgnoreConfig)
```

**Checklist:**

- [ ] Tạo `src/core/config/__init__.py`
- [ ] Tạo `src/core/config/models.py`
- [ ] Test: Import models không lỗi

---

### Task 1.2: Create Config Loader

**File:** `src/core/config/loader.py`

```python
import yaml
from fnmatch import fnmatch
from .models import ReviewerConfig

class ConfigLoader:
    CONFIG_FILENAME = ".reviewer.yaml"

    async def load(self, github, owner, repo) -> ReviewerConfig:
        """Load config from repository."""
        try:
            content = await github.get_file_content_raw(
                owner, repo, self.CONFIG_FILENAME
            )
            if content:
                data = yaml.safe_load(content)
                return ReviewerConfig(**data)
        except Exception:
            pass
        return ReviewerConfig()  # Default

    def should_ignore(self, config, file_path) -> bool:
        """Check if file should be skipped."""
        for pattern in config.ignore.paths:
            if self._match(file_path, pattern):
                return True
        return False

    def get_instructions(self, config, file_path) -> list[str]:
        """Get matching instructions for file."""
        result = []
        for pi in config.reviews.path_instructions:
            if self._match(file_path, pi.path):
                result.append(pi.instructions)
        return result

    @staticmethod
    def _match(path, pattern) -> bool:
        # Handle ** patterns
        if "**" in pattern:
            import re
            regex = pattern.replace("**", ".*").replace("*", "[^/]*")
            return bool(re.match(regex, path))
        return fnmatch(path, pattern)
```

**Checklist:**

- [ ] Tạo `src/core/config/loader.py`
- [ ] Unit test pattern matching
- [ ] Test load với sample YAML

---

## 📅 Day 2: Integration

### Task 2.1: Add GitHub Method

**File:** `src/app/services/github.py`

```python
async def get_file_content_raw(
    self, owner: str, repo: str, path: str, ref: str = "HEAD"
) -> str | None:
    """Get raw file content. Returns None if not found."""
    token = await self._get_token()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                headers={
                    **self._headers(token),
                    "Accept": "application/vnd.github.raw+json",
                },
                params={"ref": ref},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
    except:
        return None
```

**Checklist:**

- [ ] Add method to GitHubService
- [ ] Test với repo thật

---

### Task 2.2: Update Graph State

**File:** `src/agents/state.py`

```python
# Add import
from ..core.config.models import ReviewerConfig

class GraphState(TypedDict):
    # ... existing fields ...

    # NEW: Repository configuration
    repo_config: ReviewerConfig
```

**Checklist:**

- [ ] Add `repo_config` to GraphState
- [ ] Verify type checking works

---

### Task 2.3: Load Config in Context Extractor

**File:** `src/agents/nodes/context_extractor.py`

```python
from ...core.config.loader import ConfigLoader
from ...core.config.models import ReviewerConfig

async def run(state: GraphState) -> dict:
    ctx = state["context"]
    github = GitHubService(ctx.installation_id)

    # Load repository config
    loader = ConfigLoader()
    config = await loader.load(github, ctx.owner, ctx.repo)

    # Get PR files
    files = await github.get_pr_files(ctx.owner, ctx.repo, ctx.pr_number)

    # Filter ignored files
    filtered_files = [
        f for f in files
        if not loader.should_ignore(config, f["filename"])
    ]

    # ... rest of extraction ...

    return {
        "files": file_changes,
        "repo_config": config,  # NEW
    }
```

**Checklist:**

- [ ] Import ConfigLoader
- [ ] Load config at start
- [ ] Filter ignored files
- [ ] Return config in state

---

### Task 2.4: Update Agents to Use Config

**File:** `src/agents/nodes/security_agent.py` (và các agents khác)

```python
async def run(state: GraphState) -> dict:
    config = state.get("repo_config", ReviewerConfig())

    # Get threshold from config
    threshold = config.reviews.confidence_threshold

    async def process_file(file):
        # Get path instructions
        loader = ConfigLoader()
        extra = loader.get_instructions(config, file.filename)

        prompt = PROMPT.format(
            filename=file.filename,
            diff=file.patch,
            extra_instructions="\n".join(extra) if extra else "",
        )
        # ... rest ...

        # Filter by threshold
        return [c for c in comments if c.confidence >= threshold]
```

**Checklist:**

- [ ] Update security_agent.py
- [ ] Update logic_agent.py
- [ ] Update style_agent.py
- [ ] Test với config thật

---

## 📅 Day 3: Testing & Docs

### Task 3.1: Unit Tests

```python
# tests/core/config/test_models.py
def test_default_config():
    config = ReviewerConfig()
    assert config.language == "en"
    assert config.reviews.profile == "default"

def test_parse_yaml():
    yaml_str = """
    language: vi
    reviews:
      profile: chill
    """
    data = yaml.safe_load(yaml_str)
    config = ReviewerConfig(**data)
    assert config.language == "vi"

# tests/core/config/test_loader.py
def test_path_matching():
    loader = ConfigLoader()
    assert loader._match("src/api/users.py", "src/**/*.py")
    assert not loader._match("tests/test.py", "src/**/*.py")
```

**Checklist:**

- [ ] Test model validation
- [ ] Test YAML parsing
- [ ] Test path matching
- [ ] Test ignore logic

---

### Task 3.2: Documentation

- [ ] Update AGENTS.md with config info
- [ ] Create example .reviewer.yaml in repo
- [ ] Add config section to README

---

## ✅ Final Checklist

```
□ Models created and validated
□ Loader with caching works
□ GitHub method added
□ State updated
□ Context extractor loads config
□ All agents use config
□ Path matching tested
□ Ignore patterns work
□ Documentation updated
```
