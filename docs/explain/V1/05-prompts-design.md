# ✍️ Thiết kế Prompt cho AI Agents

## 1. Tổng quan

Mỗi AI agent có prompt template riêng trong thư mục `prompts/`:

- `security.py` - Phát hiện lỗ hổng bảo mật
- `style.py` - Kiểm tra code style
- `logic.py` - Tìm bugs và logic errors

## 2. Cấu trúc chung của Prompt

```
┌────────────────────────────────────────────────────────────┐
│                    Prompt Structure                        │
├────────────────────────────────────────────────────────────┤
│ 1. Role Definition                                         │
│    "You are a security expert reviewing code changes."     │
├────────────────────────────────────────────────────────────┤
│ 2. Context (Dynamic)                                       │
│    ## File: {filename}                                     │
│    ## Language: {language}                                 │
│    ## Diff: {diff}                                         │
├────────────────────────────────────────────────────────────┤
│ 3. Task Description                                        │
│    "Analyze the NEW code (+ lines) for..."                 │
├────────────────────────────────────────────────────────────┤
│ 4. Focus Areas (Domain-specific)                           │
│    - SQL injection                                         │
│    - XSS                                                   │
│    - ...                                                   │
├────────────────────────────────────────────────────────────┤
│ 5. Severity Definitions                                    │
│    - "critical": Must be fixed immediately                 │
│    - "warning": Should be reviewed                         │
│    - "info": Observation                                   │
│    - "suggestion": Best practice                           │
├────────────────────────────────────────────────────────────┤
│ 6. Rules/Constraints                                       │
│    - Only confidence > 0.7                                 │
│    - Only analyze + lines                                  │
│    - Be specific about line number                         │
├────────────────────────────────────────────────────────────┤
│ 7. Output Format (JSON)                                    │
│    {"findings": [{line, severity, message, ...}]}          │
└────────────────────────────────────────────────────────────┘
```

## 3. Security Prompt

**Focus areas:**

- SQL injection
- XSS (Cross-Site Scripting)
- Hardcoded secrets/credentials
- Path traversal
- Command injection
- SSRF
- Insecure deserialization
- Missing input validation
- Insecure cryptography

**Example output:**

```json
{
  "findings": [
    {
      "line": 42,
      "severity": "critical",
      "message": "SQL injection via string concatenation",
      "suggestion": "Use parameterized queries",
      "confidence": 0.95
    }
  ]
}
```

## 4. Style Prompt

**Focus areas:**

- Naming conventions
- Code formatting
- Function complexity
- Dead code / unused variables
- Magic numbers
- Missing comments/docstrings
- Import organization
- Type hints
- Language best practices

## 5. Logic Prompt

**Focus areas:**

- Off-by-one errors
- Null/undefined references
- Boundary conditions
- Logic flow errors
- Missing edge cases
- Wrong operators (== vs ===)
- Resource leaks
- Error handling issues
- Race conditions
- Infinite loops

## 6. Severity Levels (Thống nhất)

| Level        | Emoji | Khi nào dùng                      |
| ------------ | ----- | --------------------------------- |
| `critical`   | 🔴    | Bug/vuln chắc chắn, phải fix ngay |
| `warning`    | 🟡    | Vấn đề tiềm ẩn, cần review        |
| `info`       | 🔵    | Quan sát, không nhất thiết là lỗi |
| `suggestion` | 💡    | Best practice recommendation      |

## 7. Confidence Threshold

```python
if f.get("confidence", 0) < 0.7:
    continue  # Skip low-confidence findings
```

**Mục đích:** Giảm false positives, chỉ report những findings có độ tin cậy cao.

## 8. JSON Parsing Strategy

```python
def _parse_findings(content: str) -> list[dict]:
    # LLM có thể return text + JSON
    # Tìm phần JSON trong response
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
        return data.get("findings", [])
    return []
```

**Robust parsing:** Xử lý cả trường hợp LLM trả về text kèm JSON.

---

**Tiếp theo:** [06-data-flow.md](./06-data-flow.md) - Luồng dữ liệu chi tiết
