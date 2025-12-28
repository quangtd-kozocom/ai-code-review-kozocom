# 🔧 Autofix Documentation

> On-Demand Commands cho AI Reviewer

---

## 📚 Tài liệu

| #   | File                                       | Mô tả                                |
| --- | ------------------------------------------ | ------------------------------------ |
| 1   | [01-how-it-works.md](./01-how-it-works.md) | Kiến trúc và cách hoạt động chi tiết |
| 2   | [02-setup-guide.md](./02-setup-guide.md)   | Hướng dẫn cài đặt và cấu hình        |

---

## 🎯 Quick Start

### Supported Commands

| Command                    | Mô tả                       | Context Required        |
| -------------------------- | --------------------------- | ----------------------- |
| `@reviewer fix this`       | Generate suggested fix      | Reply to review comment |
| `@reviewer explain`        | Giải thích chi tiết issue   | Reply to review comment |
| `@reviewer generate tests` | Tạo unit tests cho PR       | Anywhere in PR          |
| `@reviewer help`           | Hiển thị danh sách commands | Anywhere in PR          |

### Demo Flow

````
┌─────────────────────────────────────────────────────────┐
│                     PR Comment Section                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔴 CRITICAL (security)                                 │
│                                                         │
│  SQL injection vulnerability detected.                  │
│  User input is directly concatenated into query.        │
│                                                         │
│  💡 Gợi ý: Use parameterized queries                    │
│                                                         │
│  ---                                                    │
│  💬 Commands:                                           │
│  - `@reviewer fix this` - Generate fix                  │
│  - `@reviewer explain` - Giải thích chi tiết            │
│                                                         │
│  └─ Reply:                                              │
│     ┌───────────────────────────────────────────┐       │
│     │ @reviewer fix this                        │       │
│     └───────────────────────────────────────────┘       │
│                                                         │
│  ↓ AI responds with:                                    │
│                                                         │
│  ## 🔧 Suggested Fix                                    │
│                                                         │
│  ```suggestion                                          │
│  cursor.execute("SELECT * FROM users WHERE id = ?",     │
│                 (user_id,))                             │
│  ```                                                    │
│                                                         │
│  **Giải thích:** Use parameterized query to prevent     │
│  SQL injection.                                         │
│                                                         │
│  [Apply suggestion] [Dismiss]                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
````

---

## 🏗️ Architecture Overview

```
GitHub Webhook
      │
      ▼
┌─────────────────┐
│    Webhooks     │───────────────┐
│   (FastAPI)     │               │
└────────┬────────┘               │
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│   review_pr     │      │ handle_command  │
│   (LangGraph)   │      │   (Chat Module) │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│  3 AI Agents    │      │  5 Handlers     │
│  (Parallel)     │      │  (Strategy)     │
└────────┬────────┘      └────────┬────────┘
         │                        │
         └────────────┬───────────┘
                      │
                      ▼
              ┌─────────────────┐
              │  GitHub API     │
              │  (Post Review)  │
              └─────────────────┘
```

---

## 📁 Module Structure

```
src/chat/
├── __init__.py      # Public exports
├── commands.py      # CommandType StrEnum (5 values)
├── context.py       # CommandContext (immutable dataclass)
├── parser.py        # parse_command() with validation
├── prompts.py       # LLM prompt templates
├── responses.py     # Response templates (success/error)
├── handler.py       # Strategy pattern handlers
└── models.py        # Pydantic models (optional)
```

---

## ✨ Features

- **🎯 On-Demand**: Developer chủ động yêu cầu khi cần
- **🔄 Interactive**: AI phản hồi trực tiếp trong PR
- **⚡ One-Click Fix**: GitHub suggestion để commit ngay
- **📚 Educational**: Giải thích giúp developer học
- **🧪 Test Generation**: Auto-generate unit tests
- **🔒 Type-Safe**: Python type hints + dataclasses

---

## 🔧 Technical Highlights

| Feature          | Implementation                        |
| ---------------- | ------------------------------------- |
| Command Parsing  | Pre-compiled regex + input validation |
| Handler Dispatch | Strategy pattern + ABC                |
| Context Passing  | Immutable frozen dataclass            |
| Error Handling   | tenacity retry + specific exceptions  |
| Type Safety      | StrEnum + type hints + Pydantic       |
| Async            | Full async/await chain                |

---

## 📊 Metrics

| Metric         | Value       |
| -------------- | ----------- |
| New files      | 8           |
| New LOC        | ~800        |
| Python version | 3.11+       |
| Commands       | 4 + unknown |
| Handlers       | 5           |

---

**Main Documentation:** [docs/code-rabbit-inspiration/autofix/](../../code-rabbit-inspiration/autofix/)
