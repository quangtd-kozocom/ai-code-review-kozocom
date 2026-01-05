# 📝 Example Configurations

> Các ví dụ `.reviewer.yaml` cho các use cases khác nhau.

---

## 1️⃣ Minimal Config

Chỉ cần thay đổi language:

```yaml
# .reviewer.yaml
language: "vi"
```

---

## 2️⃣ Python Backend Project

```yaml
# .reviewer.yaml
language: "en"

reviews:
  profile: "default"
  agents:
    - security
    - logic
    - style

  confidence_threshold: 0.75
  max_comments_per_file: 8

  path_instructions:
    - path: "src/api/**/*.py"
      instructions: |
        - Verify authentication/authorization on all endpoints
        - Check for proper error handling
        - Validate request inputs with Pydantic

    - path: "src/models/**/*.py"
      instructions: |
        - Check for SQL injection vulnerabilities
        - Verify proper use of ORM
        - Look for N+1 query issues

    - path: "src/services/**/*.py"
      instructions: |
        - Check for proper async/await usage
        - Verify error handling and logging

    - path: "tests/**/*"
      instructions: |
        - Light review - focus on coverage
        - Check for proper mocking

  auto_review:
    enabled: true
    drafts: false
    ignore_title_keywords:
      - "[WIP]"
      - "[DRAFT]"
      - "[NO REVIEW]"
    ignore_usernames:
      - dependabot[bot]
      - renovate[bot]

ignore:
  paths:
    - "**/__pycache__/**"
    - "**/migrations/**"
    - "**/.pytest_cache/**"
    - "*.lock"
    - "poetry.lock"
```

---

## 3️⃣ JavaScript/TypeScript Project

```yaml
# .reviewer.yaml
language: "en"

reviews:
  profile: "chill"

  path_instructions:
    - path: "src/components/**/*.tsx"
      instructions: |
        - Check for proper React hooks usage
        - Verify accessibility (a11y) attributes
        - Look for memory leaks in useEffect

    - path: "src/api/**/*.ts"
      instructions: |
        - Validate API error handling
        - Check for proper typing
        - Verify authentication headers

    - path: "src/utils/**/*.ts"
      instructions: |
        - Check for pure functions
        - Verify edge case handling

  auto_review:
    enabled: true
    base_branches:
      - main
      - develop

ignore:
  paths:
    - "**/node_modules/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/*.d.ts"
    - "package-lock.json"
  extensions:
    - ".min.js"
    - ".min.css"
```

---

## 4️⃣ Strict Security Review

Cho projects yêu cầu security cao:

```yaml
# .reviewer.yaml
language: "en"

reviews:
  profile: "strict"
  agents:
    - security # Security first
    - logic

  confidence_threshold: 0.6 # Lower = catch more issues
  max_comments_per_file: 20

  path_instructions:
    - path: "**/*.py"
      instructions: |
        CRITICAL SECURITY CHECKS:
        - SQL/NoSQL injection
        - XSS vulnerabilities  
        - Hardcoded secrets
        - Path traversal
        - Command injection
        - Insecure deserialization
        - Missing input validation

    - path: "src/auth/**/*"
      instructions: |
        EXTRA SCRUTINY:
        - JWT validation
        - Password handling
        - Session management
        - Rate limiting

  auto_review:
    enabled: true
    drafts: true # Review drafts too for security

ignore:
  paths:
    - "tests/**/*" # Skip tests for security review
```

---

## 5️⃣ Our Project (AI Reviewer)

```yaml
# .reviewer.yaml for hackathon/reviewer
language: "vi"

reviews:
  profile: "default"

  agents:
    - security
    - logic
    - style

  confidence_threshold: 0.7
  max_comments_per_file: 10

  path_instructions:
    - path: "src/agents/**/*.py"
      instructions: |
        - Verify structured output handling
        - Check prompt quality
        - Ensure proper async patterns
        - Validate Pydantic model usage

    - path: "src/app/api/**/*.py"
      instructions: |
        - Check webhook signature validation
        - Verify proper error responses
        - Validate request parsing

    - path: "src/chat/**/*.py"
      instructions: |
        - Check command parsing edge cases
        - Verify rate limiting logic
        - Validate GitHub API usage

    - path: "src/core/**/*.py"
      instructions: |
        - Verify LLM error handling
        - Check configuration validation

    - path: "tests/**/*"
      instructions: |
        - Focus on test coverage
        - Light style review

  auto_review:
    enabled: true
    drafts: false
    ignore_title_keywords:
      - "[WIP]"
      - "[SKIP]"
    base_branches:
      - main

chat:
  enabled: true
  allowed_commands:
    - fix
    - explain
    - tests
    - help

ignore:
  paths:
    - "**/__pycache__/**"
    - "**/.pytest_cache/**"
    - "docs/**/*.md"
    - "*.lock"
```

---

## 6️⃣ Minimal Review (CI Only)

Chỉ check security issues critical:

```yaml
# .reviewer.yaml
reviews:
  profile: "chill"
  agents:
    - security # Only security

  confidence_threshold: 0.9 # Only high confidence
  max_comments_per_file: 3

chat:
  enabled: false # No interactive commands

ignore:
  paths:
    - "tests/**/*"
    - "docs/**/*"
    - "scripts/**/*"
```

---

## 💡 Tips

1. **Start minimal** - Thêm rules dần dần
2. **Test path patterns** - Use [globster.xyz](https://globster.xyz/) to test
3. **Profile first** - Chọn profile phù hợp trước khi tune thresholds
4. **Iterate** - Adjust based on actual review results
