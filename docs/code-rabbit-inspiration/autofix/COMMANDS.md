# 📝 Commands Reference

## 🎯 Supported Commands

| Command                    | Mô Tả                        | Context                  |
| -------------------------- | ---------------------------- | ------------------------ |
| `@reviewer fix this`       | Tạo suggested fix cho issue  | Reply vào review comment |
| `@reviewer explain`        | Giải thích chi tiết về issue | Reply vào review comment |
| `@reviewer generate tests` | Tạo unit tests cho PR        | Anywhere in PR           |
| `@reviewer help`           | Hiện help                    | Anywhere                 |

---

## 💡 Usage Examples

### 1. Fix an Issue

**Step 1:** AI Reviewer posts review comment:

```markdown
🔴 **CRITICAL** (security) - SQL Injection Vulnerability

String concatenation in SQL query allows injection attacks.

**💡 Gợi ý:** Use parameterized queries

---

💬 **Commands:**

- `@reviewer fix this` - Generate fix
- `@reviewer explain` - Giải thích chi tiết
```

**Step 2:** Developer replies:

```
@reviewer fix this
```

**Step 3:** Bot generates fix:

```markdown
## 🔧 Suggested Fix

\`\`\`suggestion
cursor.execute("SELECT \* FROM users WHERE id = ?", (user_id,))
\`\`\`

**Giải thích:** Sử dụng parameterized query để tránh SQL injection.

---

_Click "Commit suggestion" để apply fix này._
```

**Step 4:** Developer clicks "Commit suggestion" ✅

---

### 2. Explain an Issue

**Developer replies to review comment:**

```
@reviewer explain
```

**Bot response:**

```markdown
## 🔍 Giải Thích Chi Tiết

### What is the problem?

SQL Injection là một kỹ thuật tấn công...

### Why is it a problem?

Attacker có thể...

### How to fix it?

1. Sử dụng parameterized queries
2. Validate input...

### Example

\`\`\`python

# ❌ Vulnerable

query = f"SELECT \* FROM users WHERE id = {user_id}"

# ✅ Safe

cursor.execute("SELECT \* FROM users WHERE id = ?", (user_id,))
\`\`\`
```

---

### 3. Generate Tests

**Developer comments anywhere in PR:**

```
@reviewer generate tests
```

hoặc với target cụ thể:

```
@reviewer generate tests for auth.py
```

**Bot response:**

```markdown
## 🧪 Generated Unit Tests

**Files analyzed:** src/auth.py, src/utils.py

\`\`\`python
import pytest
from src.auth import authenticate

def test_authenticate_valid_credentials():
"""Test successful authentication."""
result = authenticate("user@example.com", "valid_password")
assert result.success is True

def test_authenticate_invalid_password():
"""Test authentication with wrong password."""
result = authenticate("user@example.com", "wrong")
assert result.success is False

def test_authenticate_empty_email():
"""Test edge case: empty email."""
with pytest.raises(ValueError):
authenticate("", "password")
\`\`\`

---

_Copy tests này vào test file của bạn._
```

---

## 📊 Command Context Requirements

| Command          | Cần Reply vào Review Comment? | Lý do                             |
| ---------------- | ----------------------------- | --------------------------------- |
| `fix this`       | ✅ Có                         | Cần biết issue nào cần fix        |
| `explain`        | ✅ Có                         | Cần biết issue nào cần giải thích |
| `generate tests` | ❌ Không                      | Analyze toàn bộ PR                |
| `help`           | ❌ Không                      | Chỉ hiện help                     |
