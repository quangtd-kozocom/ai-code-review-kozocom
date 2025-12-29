# ⚙️ Configuration File (.reviewer.yaml)

> Cấu hình review rules per-repository

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Trung bình  
**Tham khảo:** [CodeRabbit YAML Config](https://docs.coderabbit.ai/getting-started/yaml-configuration)

---

## 📋 Mô Tả

Cho phép teams customize AI reviewer behavior qua file config trong repo:

1. **Path-based rules:** Different rules for different directories
2. **Ignore patterns:** Skip certain files/patterns
3. **Custom instructions:** Team-specific review guidelines
4. **Severity tuning:** Adjust what's critical vs warning

---

## 🎯 Mục Tiêu

- **Primary:** Per-repo customization
- **Secondary:** Reduce false positives
- **Tertiary:** Enforce team standards

---

## 💡 Configuration File

```yaml
# .reviewer.yaml

# General settings
language: vi # Response language
auto_review: true # Review on PR open
review_on_push: true # Review on new commits

# Review behavior
reviews:
  # Agents to run
  agents:
    - security
    - style
    - logic

  # Severity thresholds
  severity:
    block_merge:
      - critical
    require_comment:
      - warning
    info_only:
      - suggestion
      - info

# Path-based rules
path_instructions:
  - path: "src/api/**/*.py"
    instructions: |
      - Verify authentication on all endpoints
      - Check rate limiting
      - Validate request/response schemas

  - path: "src/models/**/*.py"
    instructions: |
      - Check for SQL injection in queries
      - Validate foreign key relationships
      - Ensure proper indexing hints

  - path: "tests/**/*"
    instructions: |
      - Light review only
      - Focus on test coverage, not style

# Files/patterns to ignore
ignore:
  paths:
    - "**/*.generated.py"
    - "**/migrations/**"
    - "**/__pycache__/**"
    - "*.lock"
    - "package-lock.json"

  # Ignore specific rules for paths
  rules:
    - path: "scripts/**"
      disable:
        - style
        - documentation

# Custom rules (AST-based)
custom_rules:
  - name: "no-print-statements"
    pattern: "print($$$)"
    message: "Use logging instead of print statements"
    severity: warning
    paths:
      - "src/**/*.py"
    exclude:
      - "scripts/**"

  - name: "no-hardcoded-secrets"
    pattern: |
      $VAR = "$SECRET"
    where:
      SECRET:
        regex: "(password|secret|api_key|token).*=.*['\"]\\w{8,}['\"]"
    message: "Potential hardcoded secret detected"
    severity: critical

# Docstring settings
docstrings:
  style: google # google, numpy, sphinx
  required_for:
    - public_functions
    - classes
  path_instructions:
    - path: "src/api/**"
      style: sphinx
      include_examples: true

# Test generation settings
tests:
  framework: pytest
  coverage_target: 80
  include_edge_cases: true
  mock_external: true

# Chat commands settings
chat:
  enabled: true
  allowed_commands:
    - fix
    - explain
    - tests
    - docstrings
    - summarize
    - re-review

  # Rate limiting
  rate_limit:
    max_commands_per_pr: 20
    cooldown_seconds: 30

# Integration settings
integrations:
  slack:
    enabled: true
    channel: "#code-reviews"
    notify_on:
      - critical_issues
      - review_complete

  jira:
    enabled: false
    project_key: "PROJ"
```

---

## 🛠️ Technical Implementation

### 1. Config Loader

```python
# src/core/config_loader.py

from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

class PathInstruction(BaseModel):
    path: str
    instructions: str
    disable: list[str] = Field(default_factory=list)

class ReviewConfig(BaseModel):
    agents: list[str] = ["security", "style", "logic"]
    severity: dict[str, list[str]] = Field(default_factory=dict)

class ReviewerConfig(BaseModel):
    """Repository-level reviewer configuration."""

    language: str = "en"
    auto_review: bool = True
    review_on_push: bool = True
    reviews: ReviewConfig = Field(default_factory=ReviewConfig)
    path_instructions: list[PathInstruction] = Field(default_factory=list)
    ignore: dict[str, Any] = Field(default_factory=dict)
    custom_rules: list[dict] = Field(default_factory=list)

class ConfigLoader:
    """Load and parse .reviewer.yaml from repository."""

    CONFIG_FILENAME = ".reviewer.yaml"

    async def load(
        self,
        github: GitHubService,
        owner: str,
        repo: str,
        ref: str = "main"
    ) -> ReviewerConfig:
        """Load config from repository."""
        try:
            content = await github.get_file_content(
                owner, repo, self.CONFIG_FILENAME, ref
            )
            if content:
                data = yaml.safe_load(content)
                return ReviewerConfig(**data)
        except Exception as e:
            log.warning("Failed to load config", error=str(e))

        return ReviewerConfig()  # Default config

    def get_instructions_for_path(
        self,
        config: ReviewerConfig,
        file_path: str
    ) -> str:
        """Get combined instructions for a file path."""
        instructions = []

        for pi in config.path_instructions:
            if self._path_matches(file_path, pi.path):
                instructions.append(pi.instructions)

        return "\n".join(instructions)

    def should_ignore_file(
        self,
        config: ReviewerConfig,
        file_path: str
    ) -> bool:
        """Check if file should be ignored."""
        ignore_paths = config.ignore.get("paths", [])

        for pattern in ignore_paths:
            if self._path_matches(file_path, pattern):
                return True

        return False

    @staticmethod
    def _path_matches(file_path: str, pattern: str) -> bool:
        """Match file path against glob pattern."""
        from fnmatch import fnmatch
        return fnmatch(file_path, pattern)
```

### 2. Integration with Agents

```python
# src/agents/nodes/security_agent.py

async def run(state: GraphState) -> dict:
    config = state.get("repo_config", ReviewerConfig())

    comments = []
    for file in state["files"]:
        # Check if file should be ignored
        if config_loader.should_ignore_file(config, file.filename):
            continue

        # Get path-specific instructions
        extra_instructions = config_loader.get_instructions_for_path(
            config, file.filename
        )

        prompt = SECURITY_PROMPT.format(
            code=file.patch,
            extra_instructions=extra_instructions,
        )

        # ... rest of agent logic
```

### 3. Custom Rules Engine

```python
# src/core/custom_rules.py

class CustomRulesEngine:
    """Execute custom AST-based rules."""

    def check(
        self,
        rules: list[dict],
        file_path: str,
        content: str
    ) -> list[RuleViolation]:
        """Check file against custom rules."""
        violations = []

        for rule in rules:
            if not self._applies_to_path(rule, file_path):
                continue

            matches = self._find_pattern(rule["pattern"], content)

            for match in matches:
                violations.append(RuleViolation(
                    rule_name=rule["name"],
                    message=rule["message"],
                    severity=rule.get("severity", "warning"),
                    line=match.line,
                    file=file_path,
                ))

        return violations
```

---

## ✅ Acceptance Criteria

1. [ ] Load `.reviewer.yaml` from repository root
2. [ ] Path-based instructions affect agent prompts
3. [ ] Ignore patterns skip files from review
4. [ ] Custom rules detect pattern violations
5. [ ] Fallback to defaults if no config

---

## 📊 Metrics

| Metric                    | Target           |
| ------------------------- | ---------------- |
| Config load time          | < 500ms          |
| False positive reduction  | -30% with tuning |
| Teams using custom config | > 50%            |

---

## 🔮 Future Enhancements

1. **Config validation:** Lint config file in PRs
2. **Config UI:** Web interface for config editing
3. **Inheritance:** Org-level defaults + repo overrides
4. **Config suggestions:** AI-suggested rules based on codebase
