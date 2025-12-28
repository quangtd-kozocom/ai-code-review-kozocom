# 🛠️ Autofix Setup Guide

Hướng dẫn cài đặt và cấu hình tính năng On-Demand Commands cho AI Reviewer.

---

## 📋 Prerequisites

Trước khi bắt đầu, đảm bảo bạn đã có:

- [x] AI Reviewer đã chạy (Phase 1 MVP completed)
- [x] GitHub App đã được cài đặt và cấu hình
- [x] Celery worker đang chạy
- [x] Python 3.11+ (required for `StrEnum`)

---

## 1. Cập nhật GitHub App Permissions

### 1.1. Thêm Webhook Events

Vào **GitHub App Settings** → **Permissions & events** → **Subscribe to events**:

| Event                          | Description            | Required          |
| ------------------------------ | ---------------------- | ----------------- |
| `Issue comments`               | Comments on issues/PRs | ✅                |
| `Pull request review comments` | Comments on code lines | ✅                |
| `Pull request reviews`         | Review submissions     | (already enabled) |
| `Pull requests`                | PR events              | (already enabled) |

### 1.2. Repository Permissions

Đảm bảo các permissions sau đã được cấp:

| Permission        | Access Level | Purpose                |
| ----------------- | ------------ | ---------------------- |
| **Contents**      | Read         | Fetch file content     |
| **Pull requests** | Write        | Create review comments |
| **Issues**        | Write        | Create issue comments  |
| **Metadata**      | Read         | (default)              |

---

## 2. Tạo Chat Module

### 2.1. Tạo cấu trúc thư mục

```bash
mkdir -p src/chat
touch src/chat/__init__.py
touch src/chat/commands.py
touch src/chat/context.py
touch src/chat/parser.py
touch src/chat/prompts.py
touch src/chat/responses.py
touch src/chat/handler.py
touch src/chat/models.py
```

### 2.2. Cài đặt dependencies mới

```bash
# Thêm tenacity cho retry logic
pip install tenacity

# Hoặc thêm vào requirements.txt
echo "tenacity>=8.2.0" >> requirements.txt
pip install -r requirements.txt
```

### 2.3. Copy code từ TASK document

Tham khảo file: `docs/code-rabbit-inspiration/autofix/TASK_IMPLEMENT_FIX_COMMAND.md`

Tạo các files theo thứ tự:

```
1. src/chat/commands.py      ← CommandType enum
2. src/chat/context.py       ← CommandContext dataclass
3. src/chat/parser.py        ← parse_command function
4. src/chat/prompts.py       ← LLM prompt templates
5. src/chat/responses.py     ← Response templates
6. src/chat/handler.py       ← All handlers
7. src/chat/__init__.py      ← Exports
8. src/chat/models.py        ← (Optional) Pydantic models
```

---

## 3. Cập nhật GitHub Service

### 3.1. Thêm imports

```python
# src/app/services/github.py

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from httpx import HTTPStatusError
```

### 3.2. Thêm methods mới

Copy 5 methods từ TASK document vào `GitHubService` class:

- `get_review_comment()`
- `get_file_content_at_pr()`
- `create_issue_comment()`
- `create_review_comment_reply()`
- `_headers()` helper
- `_format_code_context()` helper

---

## 4. Cập nhật Webhooks

### 4.1. Update webhooks.py

```python
# src/app/api/v1/webhooks.py

from enum import StrEnum

class GitHubEvent(StrEnum):
    PULL_REQUEST = "pull_request"
    ISSUE_COMMENT = "issue_comment"
    REVIEW_COMMENT = "pull_request_review_comment"
```

### 4.2. Thêm event handlers

Copy code từ TASK document:

- `_handle_pull_request()` - existing, refactored
- `_handle_issue_comment()` - NEW
- `_handle_review_comment()` - NEW

### 4.3. Update main handler với pattern matching

```python
match x_github_event:
    case GitHubEvent.PULL_REQUEST:
        return _handle_pull_request(payload)
    case GitHubEvent.ISSUE_COMMENT:
        return _handle_issue_comment(payload)
    case GitHubEvent.REVIEW_COMMENT:
        return _handle_review_comment(payload)
    case _:
        return {"status": "ignored"}
```

---

## 5. Thêm Celery Task

### 5.1. Update tasks.py

```python
# src/workers/tasks.py

from ..chat.commands import CommandType
from ..chat.context import CommandContext
from ..chat.handler import CommandHandler
from ..chat.parser import parse_command

@celery_app.task(bind=True, max_retries=3)
def handle_command(
    self,
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    comment_body: str,
    author: str,
    installation_id: int,
    in_reply_to_id: int | None = None,
):
    """Handle @reviewer command from PR comment."""
    # ... implementation
```

---

## 6. Cập nhật Review Comments (CTA)

### 6.1. Update github_publisher.py

Thêm Call-to-Action vào review comments:

```python
# src/agents/nodes/github_publisher.py

CTA_TEMPLATE = """
---
💬 **Commands:**
- `@reviewer fix this` - Generate fix
- `@reviewer explain` - Giải thích chi tiết
"""

def format_comment(comment):
    # ... existing formatting ...

    # Add CTA for critical/warning issues
    if comment.severity in (Severity.CRITICAL, Severity.WARNING):
        body += CTA_TEMPLATE

    return body
```

---

## 7. Testing

### 7.1. Run Unit Tests

```bash
# Test parser
pytest tests/unit/test_chat_parser.py -v

# Test context
pytest tests/unit/test_command_context.py -v

# Run all tests
pytest tests/ -v
```

### 7.2. Manual Testing

#### Test 1: Fix Command

1. Tạo một PR với code có issue
2. Đợi AI Reviewer comment
3. Reply vào review comment: `@reviewer fix this`
4. Verify: AI tạo suggestion block

#### Test 2: Explain Command

1. Reply vào review comment: `@reviewer explain`
2. Verify: AI giải thích chi tiết issue

#### Test 3: Generate Tests

1. Comment ở bất kỳ đâu trong PR: `@reviewer generate tests`
2. Verify: AI generate unit tests

#### Test 4: Help Command

1. Comment: `@reviewer help`
2. Verify: AI hiển thị command table

---

## 8. Verification Checklist

### Chat Module

- [ ] `src/chat/__init__.py` exports all public APIs
- [ ] `src/chat/commands.py` has `CommandType` enum
- [ ] `src/chat/context.py` has `CommandContext` dataclass
- [ ] `src/chat/parser.py` parses 4 commands
- [ ] `src/chat/prompts.py` has LLM templates
- [ ] `src/chat/responses.py` has response templates
- [ ] `src/chat/handler.py` has 5 handlers

### GitHub Service

- [ ] `get_review_comment` works
- [ ] `get_file_content_at_pr` works
- [ ] `create_issue_comment` works
- [ ] `create_review_comment_reply` works

### Webhooks

- [ ] Handles `issue_comment` events
- [ ] Handles `pull_request_review_comment` events
- [ ] Pattern matching works correctly

### Tasks

- [ ] `handle_command` task registered
- [ ] Uses `CommandContext` properly

### Review Publisher

- [ ] CTA shows on critical/warning comments

---

## 9. Troubleshooting

### 9.1. Command không được nhận

**Nguyên nhân:** Webhook event chưa được subscribe

**Fix:**

1. Vào GitHub App Settings
2. Enable `Issue comments` và `Pull request review comments`
3. Save changes

### 9.2. "Không tìm thấy review comment"

**Nguyên nhân:** Đang comment ở conversation (issue comment), không phải code (review comment)

**Fix:** Reply trực tiếp vào review comment trên code line

### 9.3. Fix suggestion không hiện

**Nguyên nhân:** LLM response không parse được

**Check logs:**

```bash
docker logs reviewer-worker 2>&1 | grep "Failed to parse"
```

### 9.4. Permission denied

**Nguyên nhân:** GitHub App thiếu permissions

**Fix:**

1. Check GitHub App → Permissions
2. Ensure `Pull requests: Write` và `Issues: Write`

---

## 10. Environment Variables

Không cần thêm env vars mới. Sử dụng existing:

```env
# Existing vars
GITHUB_APP_ID=xxx
GITHUB_PRIVATE_KEY=xxx
GITHUB_WEBHOOK_SECRET=xxx
GEMINI_API_KEY=xxx
REDIS_URL=redis://localhost:6379
```

---

## 11. Production Deployment

### 11.1. Restart Services

```bash
# Restart all services
./stop.sh
./start.sh

# Or individually
docker-compose restart worker
docker-compose restart api
```

### 11.2. Verify Webhook

```bash
# Check webhook delivery
# Go to: GitHub App → Advanced → Recent Deliveries

# Check for successful 200 responses
```

### 11.3. Monitor Logs

```bash
# Watch worker logs
docker-compose logs -f worker

# Watch API logs
docker-compose logs -f api
```

---

## 12. Next Steps

- [ ] **Rate Limiting**: Implement per-user command rate limit
- [ ] **Analytics**: Track command usage
- [ ] **Custom Prompts**: Allow repo-specific prompt customization
- [ ] **More Commands**: Add `@reviewer refactor`, `@reviewer document`

---

**Quay lại:** [01-how-it-works.md](./01-how-it-works.md) - Cách tính năng hoạt động
