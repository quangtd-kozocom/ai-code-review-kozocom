# 📐 Our Configuration Schema

> Schema cho `.reviewer.yaml` của project chúng ta.

---

## 📁 File Location

```
repository-root/
├── .reviewer.yaml    ← Config file
├── src/
├── tests/
└── ...
```

---

## 📋 Complete Schema

```yaml
# .reviewer.yaml
# AI Code Reviewer Configuration

# ═══════════════════════════════════════════════════════════
# GENERAL SETTINGS
# ═══════════════════════════════════════════════════════════

# Response language: "en" | "vi" | "ja" | etc.
language: "en"

# ═══════════════════════════════════════════════════════════
# REVIEWS CONFIGURATION
# ═══════════════════════════════════════════════════════════
reviews:
  # ─────────────────────────────────────────────────────────
  # Review Profile
  # ─────────────────────────────────────────────────────────
  # Options: "chill" | "default" | "strict"
  # - chill: Suggestions only, higher threshold
  # - default: Balanced
  # - strict: More warnings, lower threshold
  profile: "default"

  # ─────────────────────────────────────────────────────────
  # Agents to Run
  # ─────────────────────────────────────────────────────────
  # Available: security, logic, style
  agents:
    - security
    - logic
    - style

  # ─────────────────────────────────────────────────────────
  # Thresholds
  # ─────────────────────────────────────────────────────────
  # Minimum confidence to report (0.0 - 1.0)
  confidence_threshold: 0.7

  # Maximum comments per file
  max_comments_per_file: 10

  # ─────────────────────────────────────────────────────────
  # Path Instructions
  # ─────────────────────────────────────────────────────────
  # Custom instructions for specific paths
  path_instructions:
    - path: "src/api/**/*.py"
      instructions: |
        - Verify authentication on endpoints
        - Check rate limiting

    - path: "tests/**/*"
      instructions: |
        - Light review only
        - Focus on coverage

  # ─────────────────────────────────────────────────────────
  # Auto Review Settings
  # ─────────────────────────────────────────────────────────
  auto_review:
    # Enable automatic reviews
    enabled: true

    # Review draft PRs
    drafts: false

    # Skip PRs with these keywords in title
    ignore_title_keywords:
      - "[WIP]"
      - "[SKIP REVIEW]"

    # Only review PRs targeting these branches
    base_branches: [] # Empty = all branches

    # Skip PRs from these users
    ignore_usernames:
      - dependabot[bot]

# ═══════════════════════════════════════════════════════════
# CHAT CONFIGURATION
# ═══════════════════════════════════════════════════════════
chat:
  # Enable @reviewer commands
  enabled: true

  # Allowed commands
  allowed_commands:
    - fix
    - explain
    - tests
    - help

  # Rate limiting
  rate_limit:
    max_per_pr: 20
    cooldown_seconds: 30

# ═══════════════════════════════════════════════════════════
# IGNORE PATTERNS
# ═══════════════════════════════════════════════════════════
ignore:
  # Glob patterns for files to skip
  paths:
    - "**/__pycache__/**"
    - "**/migrations/**"
    - "**/*.generated.*"
    - "*.lock"
    - "package-lock.json"

  # File extensions to skip
  extensions:
    - ".min.js"
    - ".min.css"
```

---

## 🔤 Field Descriptions

### General

| Field      | Type   | Default | Description            |
| ---------- | ------ | ------- | ---------------------- |
| `language` | string | `"en"`  | Response language code |

### Reviews

| Field                           | Type      | Default                          | Description       |
| ------------------------------- | --------- | -------------------------------- | ----------------- |
| `reviews.profile`               | enum      | `"default"`                      | Review strictness |
| `reviews.agents`                | list[str] | `["security", "logic", "style"]` | Agents to run     |
| `reviews.confidence_threshold`  | float     | `0.7`                            | Min confidence    |
| `reviews.max_comments_per_file` | int       | `10`                             | Limit per file    |
| `reviews.path_instructions`     | list      | `[]`                             | Per-path rules    |

### Auto Review

| Field                               | Type      | Default | Description       |
| ----------------------------------- | --------- | ------- | ----------------- |
| `auto_review.enabled`               | bool      | `true`  | Auto review on PR |
| `auto_review.drafts`                | bool      | `false` | Include drafts    |
| `auto_review.ignore_title_keywords` | list[str] | `[]`    | Skip keywords     |
| `auto_review.base_branches`         | list[str] | `[]`    | Branch filter     |
| `auto_review.ignore_usernames`      | list[str] | `[]`    | User filter       |

### Chat

| Field                   | Type      | Default                               | Description      |
| ----------------------- | --------- | ------------------------------------- | ---------------- |
| `chat.enabled`          | bool      | `true`                                | Enable commands  |
| `chat.allowed_commands` | list[str] | `["fix", "explain", "tests", "help"]` | Allowed commands |

### Ignore

| Field               | Type      | Default | Description     |
| ------------------- | --------- | ------- | --------------- |
| `ignore.paths`      | list[str] | `[]`    | Glob patterns   |
| `ignore.extensions` | list[str] | `[]`    | File extensions |

---

## 🎭 Profile Behaviors

| Profile   | `confidence_threshold` | `max_comments_per_file` | Severity Bias    |
| --------- | ---------------------- | ----------------------- | ---------------- |
| `chill`   | 0.85                   | 5                       | Suggestions only |
| `default` | 0.7                    | 10                      | Balanced         |
| `strict`  | 0.6                    | 15                      | More warnings    |

---

## 🔀 Path Instruction Matching

```python
# Matching logic
- "src/**/*.py"       # All .py files under src/
- "tests/**/*"        # All files under tests/
- "*.md"              # All .md files in root
- "src/api/*.py"      # Only .py files directly in src/api/
```

**Khi nhiều patterns match:** Instructions được **combine** theo thứ tự.
