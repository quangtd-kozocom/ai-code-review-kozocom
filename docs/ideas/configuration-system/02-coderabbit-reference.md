# 🔍 CodeRabbit Configuration Reference

> Tài liệu này tổng hợp cách CodeRabbit thiết kế configuration system.  
> Nguồn: [docs.coderabbit.ai/reference/configuration](https://docs.coderabbit.ai/reference/configuration)

---

## 📁 File Location

CodeRabbit sử dụng file `.coderabbit.yaml` đặt ở **root** của repository.

---

## 🔀 Configuration Resolution Order

CodeRabbit hỗ trợ nhiều nguồn config với ưu tiên (cao → thấp):

```
1. Repository YAML file (.coderabbit.yaml)   ← Cao nhất
2. Repository web interface settings
3. Central configuration (org-wide)
4. Default values                            ← Thấp nhất
```

**Takeaway cho chúng ta**: Phase 1 chỉ cần YAML + Defaults.

---

## 📋 Configuration Sections

CodeRabbit chia config thành 4 sections chính:

### 1️⃣ General Settings

```yaml
language: "en-US" # Ngôn ngữ response
tone_instructions: "" # Tone tuỳ chỉnh
early_access: false # Beta features
```

### 2️⃣ Reviews

```yaml
reviews:
  profile: "chill" # chill | assertive
  request_changes_workflow: false
  high_level_summary: true
  sequence_diagrams: true
  poem: true # Fun feature

  path_filters: [] # Files to include/exclude
  path_instructions: [] # Per-path rules

  auto_review:
    enabled: true
    drafts: false
    ignore_title_keywords: []
    base_branches: []

  tools: # Linting tools
    ruff:
      enabled: true
    shellcheck:
      enabled: true
```

### 3️⃣ Chat

```yaml
chat:
  auto_reply: true # Tự động reply mentions
  art: true # ASCII art
```

### 4️⃣ Knowledge Base

```yaml
knowledge_base:
  opt_out: false
  learnings:
    scope: "auto" # local | global | auto
  code_guidelines:
    enabled: true
```

---

## 🎯 Path Instructions (Quan Trọng)

Đây là feature **quan trọng nhất** cho chúng ta:

```yaml
reviews:
  path_instructions:
    - path: "src/api/**/*.py"
      instructions: |
        - Check authentication on all endpoints
        - Verify rate limiting
        - Validate request schemas

    - path: "tests/**/*"
      instructions: |
        - Light review only
        - Focus on test coverage

    - path: "src/models/**/*.py"
      instructions: |
        - Check for SQL injection
        - Verify ORM usage
```

**Cách hoạt động:**

1. Mỗi file được match với patterns
2. Instructions được inject vào agent prompts
3. Nhiều patterns có thể match → combine instructions

---

## ⚙️ Auto Review Settings

Control tự động review:

```yaml
reviews:
  auto_review:
    enabled: true # Bật/tắt auto review
    auto_incremental_review: true # Review khi push thêm
    drafts: false # Review draft PRs không?

    ignore_title_keywords: # Skip PRs có từ này trong title
      - "[WIP]"
      - "[SKIP REVIEW]"
      - "DO NOT MERGE"

    base_branches: # Chỉ review PR vào branches này
      - main
      - develop

    ignore_usernames: # Skip PRs từ users này
      - dependabot
      - renovate[bot]

    labels: [] # Chỉ review PR có labels này
```

---

## 🎭 Review Profiles

CodeRabbit có 2 profiles chính:

| Profile     | Behavior                                      |
| ----------- | --------------------------------------------- |
| `chill`     | Ít comments hơn, suggestions thay vì warnings |
| `assertive` | Strict hơn, nhiều warnings, REQUEST_CHANGES   |

---

## 📌 Key Takeaways

Những thứ chúng ta **nên implement** (Phase 1):

| Feature                     | Priority     | Reason               |
| --------------------------- | ------------ | -------------------- |
| `language`                  | High         | Hỗ trợ tiếng Việt    |
| `reviews.profile`           | High         | Customize strictness |
| `reviews.path_instructions` | **Critical** | Core feature         |
| `reviews.auto_review`       | High         | Control triggers     |
| `ignore.paths`              | High         | Reduce noise         |
| `chat.enabled`              | Medium       | Control commands     |

Những thứ **bỏ qua** (Phase 1):

| Feature             | Reason                  |
| ------------------- | ----------------------- |
| `poem`, `art`       | Fun but not essential   |
| `sequence_diagrams` | Complex, Phase 2        |
| `knowledge_base`    | Separate feature        |
| `tools.*` (linters) | We use LLM, not linters |
