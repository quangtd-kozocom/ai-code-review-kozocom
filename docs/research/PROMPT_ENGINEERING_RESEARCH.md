# 🔬 Prompt Engineering Research - AI Code Reviewer

> **Mục tiêu**: Phân tích và đề xuất cải thiện các prompt trong dự án AI Code Reviewer dựa trên best practices từ [Prompt Engineering Guide](https://www.promptingguide.ai/)

**Ngày tạo**: 2025-12-29  
**Trạng thái**: Draft  
**Tác giả**: AI Code Reviewer Team

---

## 📑 Mục Lục

1. [Tổng Quan Prompt Engineering](#1-tổng-quan-prompt-engineering)
2. [Phân Tích Prompt Hiện Tại](#2-phân-tích-prompt-hiện-tại)
3. [Các Kỹ Thuật Prompting Quan Trọng](#3-các-kỹ-thuật-prompting-quan-trọng)
4. [Đề Xuất Cải Thiện Chi Tiết](#4-đề-xuất-cải-thiện-chi-tiết)
5. [Action Items & Roadmap](#5-action-items--roadmap)
6. [Tài Liệu Tham Khảo](#6-tài-liệu-tham-khảo)

---

## 1. Tổng Quan Prompt Engineering

### 1.1 Prompt Engineering Là Gì?

Prompt engineering là kỹ thuật thiết kế và tối ưu hóa prompt để sử dụng hiệu quả các language models (LMs). Kỹ năng này giúp:

- **Hiểu capabilities và limitations** của LLM
- **Cải thiện độ chính xác** trong các task phức tạp như code review
- **Tăng tính nhất quán** của output
- **Giảm hallucination** và sai sót

### 1.2 Các Thành Phần Của Một Prompt

Theo Prompting Guide, một prompt hiệu quả bao gồm:

| Thành Phần           | Mô Tả                                | Ví Dụ                                               |
| -------------------- | ------------------------------------ | --------------------------------------------------- |
| **Instruction**      | Task cụ thể cần thực hiện            | "Analyze the NEW code for security vulnerabilities" |
| **Context**          | Thông tin bổ sung để hướng dẫn model | File context, language, diff format                 |
| **Input Data**       | Dữ liệu đầu vào cần xử lý            | Code diff, file content                             |
| **Output Indicator** | Định dạng output mong muốn           | JSON schema, markdown format                        |

### 1.3 Tại Sao Prompt Engineering Quan Trọng Cho Code Reviewer?

```
Code Review = Complex Reasoning Task + Code Understanding + Domain Knowledge

→ Cần prompt engineering nâng cao để đạt kết quả tốt
```

---

## 2. Phân Tích Prompt Hiện Tại

### 2.1 Tổng Quan Các Prompt

Có **6 prompt chính** trong codebase:

#### **Agents Prompts** (`src/agents/prompts/`)

| File          | Mục Đích                        | Độ Dài    | Kỹ Thuật Hiện Tại       |
| ------------- | ------------------------------- | --------- | ----------------------- |
| `security.py` | Review security vulnerabilities | ~50 lines | Zero-shot + JSON output |
| `logic.py`    | Review logic errors/bugs        | ~54 lines | Zero-shot + JSON output |
| `style.py`    | Review code style               | ~51 lines | Zero-shot + JSON output |

#### **Chat Prompts** (`src/chat/prompts.py`)

| Prompt                  | Mục Đích                  | Độ Dài    | Kỹ Thuật Hiện Tại       |
| ----------------------- | ------------------------- | --------- | ----------------------- |
| `FIX_PROMPT`            | Generate fix cho issue    | ~25 lines | Zero-shot + JSON output |
| `EXPLAIN_PROMPT`        | Giải thích issue chi tiết | ~22 lines | Zero-shot + Markdown    |
| `GENERATE_TESTS_PROMPT` | Tạo unit tests            | ~28 lines | Zero-shot + Code block  |

---

### 2.2 Phân Tích Chi Tiết Từng Prompt

#### 🔒 **SECURITY_PROMPT**

**Hiện tại:**

```python
"""You are a security expert reviewing code changes.

## File: {filename}
## Language: {language}

## Diff (lines starting with + are additions):
```

{diff}

```

## Task:
Analyze the NEW code (+ lines) for security vulnerabilities.

## Focus on:
- SQL injection
- XSS (Cross-Site Scripting)
- Hardcoded secrets/credentials
...

## Severity Levels (MUST use exactly one of these):
- "critical": Definite security vulnerability...
- "warning": Potential security issue...
- "info": Security-related observation...
- "suggestion": Best practice recommendation...

## Rules:
1. Only report issues with confidence > 0.7
2. Only analyze NEW code (+ lines)
...

## Output (JSON only, no markdown):
{{"findings": [...]}}
"""
```

**Điểm mạnh ✅:**

- Clear instruction
- Structured output format (JSON)
- Explicit severity levels
- Specific focus areas
- Rules rõ ràng

**Điểm yếu ⚠️:**

- **Thiếu Few-shot examples**: Không có ví dụ về output mong muốn
- **Thiếu reasoning guidance**: Không hướng dẫn model "think step by step"
- **Thiếu context về project**: Không biết tech stack, framework
- **Quá generic**: Không tailored cho specific languages/frameworks
- **Không có negative examples**: Không chỉ rõ "đừng làm gì"

---

#### 🧠 **LOGIC_PROMPT**

**Phân tích tương tự SECURITY_PROMPT với các vấn đề:**

- ❌ Thiếu Chain-of-Thought guidance
- ❌ Không có ví dụ về false positives cần tránh
- ❌ Thiếu context về business logic của project

---

#### 🎨 **STYLE_PROMPT**

**Vấn đề đặc biệt:**

- ❌ "Don't be overly pedantic" - nói điều KHÔNG nên làm thay vì nên làm gì
- ❌ Thiếu specific style guide references (PEP8, ESLint configs, etc.)

---

#### 🔧 **FIX_PROMPT**

**Hiện tại:**

```python
"""You are an expert code fixer.

## Issue from Code Review:
{issue_description}

## File: {file_path}
## Line: {line}

## Code Context (lines around the issue):
```

{code_context}

```

## Task:
Generate a MINIMAL fix for this issue. Only fix the problematic line(s).

## Rules:
1. Keep the SAME indentation as the original code
2. Only output the fixed code, nothing else
3. Be concise - minimal changes only
4. Ensure the fix is syntactically correct

## Output Format (JSON only, no markdown):
{{"fixed_code": "the corrected code line(s)", "explanation": "brief 1-sentence explanation"}}
"""
```

**Điểm yếu ⚠️:**

- ❌ Thiếu ví dụ fix thành công
- ❌ Không có guidance về edge cases
- ❌ Thiếu context về codebase's conventions

---

#### 📚 **EXPLAIN_PROMPT**

**Điểm mạnh ✅:**

- Good structure (What, Why, How, Example)
- Educational tone specified

**Điểm yếu ⚠️:**

- ❌ Thiếu target audience clarity (junior dev level)
- ❌ Không có ví dụ về explanation format mong muốn

---

#### 🧪 **GENERATE_TESTS_PROMPT**

**Điểm yếu nghiêm trọng ⚠️:**

- ❌ Quá vague về "comprehensive"
- ❌ Thiếu test naming conventions
- ❌ Không có ví dụ về test structure mong muốn
- ❌ Missing context về existing test patterns trong project

---

### 2.3 Tổng Hợp Các Vấn Đề Chung

| Vấn Đề                               | Mức Độ      | Ảnh Hưởng                 |
| ------------------------------------ | ----------- | ------------------------- |
| **Thiếu Few-shot Examples**          | 🔴 Critical | Output không consistent   |
| **Không có Chain-of-Thought**        | 🔴 Critical | Miss complex issues       |
| **Thiếu Negative Examples**          | 🟡 Medium   | False positives cao       |
| **Generic, không context-aware**     | 🟡 Medium   | Không phù hợp với project |
| **Nói "đừng làm" thay vì "hãy làm"** | 🟢 Low      | Model có thể ignore       |

---

## 3. Các Kỹ Thuật Prompting Quan Trọng

### 3.1 Zero-Shot Prompting (Hiện Tại)

**Định nghĩa:** Prompt không chứa examples, chỉ có instruction.

**Ưu điểm:**

- Đơn giản, dễ maintain
- Prompt ngắn, tiết kiệm tokens

**Nhược điểm:**

- Kém hiệu quả với complex tasks
- Output không consistent
- Khó kiểm soát format chính xác

> ⚠️ **Hiện tại tất cả prompts đang dùng Zero-shot** - cần nâng cấp!

---

### 3.2 Few-Shot Prompting (Nên Áp Dụng)

**Định nghĩa:** Cung cấp 1-5 examples trong prompt.

**Nghiên cứu chứng minh:**

> "Few-shot prompting can be used as a technique to enable in-context learning where we provide demonstrations in the prompt to steer the model to better performance."
> — [Few-Shot Prompting](https://www.promptingguide.ai/techniques/fewshot)

**Ví dụ áp dụng cho Security Prompt:**

```python
SECURITY_PROMPT_IMPROVED = """
You are a security expert reviewing code changes.

## Example 1 - SQL Injection:
Input diff:
```

- query = f"SELECT \* FROM users WHERE id = {user_id}"

```
Output:
{{"findings": [{
    "line": 1,
    "severity": "critical",
    "message": "SQL injection via f-string interpolation",
    "suggestion": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "confidence": 0.95
}]}}

## Example 2 - No Issue Found:
Input diff:
```

- user = db.session.query(User).filter(User.id == user_id).first()

```
Output:
{{"findings": []}}

## Now analyze this code:
...
"""
```

**Benefits:**

- ✅ Model hiểu chính xác format mong muốn
- ✅ Consistent output structure
- ✅ Giảm false positives với negative examples

---

### 3.3 Chain-of-Thought (CoT) Prompting (Highly Recommended!)

**Định nghĩa:** Hướng dẫn model suy nghĩ từng bước trước khi đưa ra kết luận.

**Nghiên cứu:**

> "Chain-of-thought (CoT) prompting enables complex reasoning capabilities through intermediate reasoning steps."
> — [CoT Prompting](https://www.promptingguide.ai/techniques/cot)

**Cách áp dụng đơn giản - Zero-shot CoT:**

```python
# Thêm câu này vào cuối instruction
"Let's analyze this step by step:
1. First, identify what the code is doing
2. Then, consider potential security implications
3. Finally, assess the severity and provide recommendation"
```

**Ví dụ cho Logic Review:**

```python
LOGIC_PROMPT_WITH_COT = """
You are a code logic expert reviewing code changes.

## Task:
Analyze the code step by step:
1. **Understand**: What is this code trying to do?
2. **Trace**: Walk through the execution path mentally
3. **Identify**: Find potential logic errors
4. **Verify**: Double-check your findings with confidence scores
5. **Report**: Only report issues with confidence > 0.7

## Thinking Process Example:
For code: `for i in range(len(items) + 1): process(items[i])`
Thought:
- The loop goes from 0 to len(items) inclusive
- This means it tries to access items[len(items)]
- Array indices go from 0 to len-1
- This is an off-by-one error causing IndexError
Finding: Off-by-one error at line X, confidence 0.92

## Now analyze:
...
"""
```

---

### 3.4 Tree of Thoughts (ToT) - Advanced

**Định nghĩa:** Multiple reasoning paths, self-evaluation, có thể backtrack.

**Simplified Version cho Code Review:**

```python
"""
Imagine three security experts are reviewing this code:
- Expert 1 focuses on input validation
- Expert 2 focuses on authentication/authorization
- Expert 3 focuses on data exposure

Each expert analyzes the code and shares findings.
If any expert is not confident (<0.7), they abstain.
Combine all findings into the final report.
"""
```

---

### 3.5 Specificity - Best Practices

Theo Prompting Guide:

> "Be very specific about the instruction and task you want the model to perform. The more descriptive and detailed the prompt is, the better the results."

**❌ Avoid:**

```python
"Don't be too pedantic"  # Vague, negative instruction
```

**✅ Better:**

```python
"Focus on issues that would affect code maintainability in a team setting.
Ignore formatting issues that would be auto-fixed by linters."
```

---

### 3.6 "To Do" vs "Not To Do"

Theo best practices:

> "Avoid saying what not to do but say what to do instead. This encourages more specificity."

**❌ Current (style.py):**

```python
"Don't be overly pedantic - focus on meaningful issues"
```

**✅ Improved:**

```python
"Focus on issues that impact:
- Code readability for new team members
- Long-term maintainability
- Team coding standards consistency
Skip issues that are purely stylistic without functional impact."
```

---

## 4. Đề Xuất Cải Thiện Chi Tiết

### 4.1 Cải Thiện SECURITY_PROMPT

#### Priority: 🔴 HIGH

**Changes:**

```python
SECURITY_PROMPT_V2 = """
You are a senior security engineer at a tech company, reviewing code changes in a pull request.

## Context
- File: {filename}
- Language: {language}
- Framework: {framework}  # NEW: Add framework context

## Code Changes (lines starting with + are additions):
```

{diff}

````

## Your Task
Analyze ONLY the new code (+ lines) for security vulnerabilities.
Think step by step before making conclusions.

## Analysis Process
1. **Identify**: What does this new code do?
2. **Threat Model**: What could an attacker exploit here?
3. **Assess**: How severe would successful exploitation be?
4. **Recommend**: What's the minimal fix?

## Examples

### Example 1: SQL Injection (Critical)
Input:
```python
+ query = f"SELECT * FROM users WHERE email = '{email}'"
+ cursor.execute(query)
````

Analysis: User input email is directly interpolated into SQL query.
Output:
{{"findings": [{{
    "line": 1,
    "severity": "critical",
    "message": "SQL injection vulnerability - user input directly in query",
    "suggestion": "Use parameterized query: cursor.execute('SELECT * FROM users WHERE email = ?', (email,))",
    "confidence": 0.95
}}]}}

### Example 2: Safe Code (No Issue)

Input:

```python
+ user = User.query.filter_by(email=email).first()
```

Analysis: Using ORM's filter_by which auto-escapes parameters.
Output:
{{"findings": []}}

### Example 3: Potential Issue Needs Review (Warning)

Input:

```python
+ headers = {{"Authorization": auth_header}}
+ response = requests.get(url, headers=headers)
```

Analysis: Sending auth header to external URL - might be intentional but could be credential leak.
Output:
{{"findings": [{{
    "line": 2,
    "severity": "warning",
    "message": "Credentials being sent to external URL - verify this is intentional",
    "suggestion": "Ensure 'url' is a trusted endpoint or use environment-specific configuration",
    "confidence": 0.75
}}]}}

## Vulnerability Categories to Check

- SQL/NoSQL injection
- XSS (Cross-Site Scripting)
- Hardcoded secrets/credentials
- Path traversal
- Command injection
- SSRF (Server-Side Request Forgery)
- Insecure deserialization
- Missing input validation
- Insecure cryptography

## Rules

1. Report ONLY issues with confidence > 0.7
2. Analyze ONLY new code (+ lines)
3. If no issues found, return empty findings array
4. Use ONLY these severity values: critical, warning, info, suggestion

## Output (JSON only):

{{"findings": [...]}}
"""

````

---

### 4.2 Cải Thiện LOGIC_PROMPT

#### Priority: 🔴 HIGH

**Key Changes:**
- Add CoT reasoning process
- Add examples with reasoning traces
- Add language-specific edge cases

```python
LOGIC_PROMPT_V2 = """
You are a senior software engineer debugging code in a code review.

## Context
- File: {filename}
- Language: {language}

## Code Changes:
````

{diff}

````

## Your Task
Find logic errors and potential bugs in the NEW code (+ lines).

## Reasoning Process (Think Step by Step)
For each suspicious code section:
1. **What**: What is this code trying to accomplish?
2. **Trace**: Walk through execution with sample inputs
3. **Edge Cases**: What happens with null, empty, boundary values?
4. **Verify**: Am I confident this is actually a bug?

## Examples with Reasoning

### Example 1: Off-by-one Error
```python
+ for i in range(len(items) + 1):
+     process(items[i])
````

Reasoning:

- Code loops from 0 to len(items) inclusive
- Arrays are 0-indexed, valid indices are 0 to len-1
- When i = len(items), items[i] causes IndexError
  Verdict: Definite bug, confidence 0.95
  Output: {{"findings": [{{
      "line": 1,
      "severity": "critical",
      "message": "Off-by-one error - loop iterates beyond array bounds",
      "suggestion": "Use range(len(items)) instead of range(len(items) + 1)",
      "confidence": 0.95
  }}]}}

### Example 2: Potential Null Reference

```python
+ user = get_user(user_id)
+ print(user.name)
```

Reasoning:

- get_user might return None if user not found
- Accessing .name on None causes AttributeError
- Common pattern but depends on get_user implementation
  Verdict: Potential issue, needs null check
  Output: {{"findings": [{{
      "line": 2,
      "severity": "warning",
      "message": "Potential None reference - user might not exist",
      "suggestion": "Add null check: if user: print(user.name)",
      "confidence": 0.80
  }}]}}

### Example 3: False Positive to Avoid

```python
+ if user is None:
+     raise ValueError("User not found")
+ print(user.name)
```

Reasoning:

- There's already a null check before accessing user.name
- This is safe code
  Output: {{"findings": []}}

## Focus Areas

- Off-by-one errors
- Null/undefined references
- Boundary conditions
- Logic flow errors
- Missing edge cases
- Incorrect operators (== vs ===, && vs ||)
- Resource leaks
- Error handling gaps
- Race conditions
- Infinite loops/recursion

## Rules

1. Only report confidence > 0.7
2. Only analyze NEW code (+ lines)
3. Empty findings array if no issues
4. Severity: critical/warning/info/suggestion

## Output (JSON only):

{{"findings": [...]}}
"""

````

---

### 4.3 Cải Thiện STYLE_PROMPT

#### Priority: 🟡 MEDIUM

**Key Changes:**
- Replace negative instructions with positive ones
- Add language-specific style guides
- Add examples

```python
STYLE_PROMPT_V2 = """
You are a code reviewer focusing on code quality and maintainability.

## Context
- File: {filename}
- Language: {language}
- Style Guide: {style_guide}  # e.g., "PEP8", "Google Style", "ESLint Airbnb"

## Code Changes:
````

{diff}

````

## Your Task
Review NEW code (+ lines) for style and maintainability issues.

## Focus On Issues That Impact
✅ Code readability for new team members
✅ Long-term maintainability
✅ Team coding standards consistency
✅ Self-documenting code quality

## Skip Issues That Are
- Auto-fixable by formatters (spacing, line length)
- Purely subjective preferences
- Minor inconsistencies with no practical impact

## Examples

### Example 1: Poor Naming (Suggestion)
```python
+ def p(x, y):
+     return x * y + TAX_RATE
````

Issue: Function name 'p' and parameters 'x', 'y' are not descriptive
Output: {{"findings": [{{
    "line": 1,
    "severity": "suggestion",
    "message": "Function and parameter names are not descriptive",
    "suggestion": "Use descriptive names: def calculate_price(base_price, quantity): return base_price * quantity + TAX_RATE",
    "confidence": 0.90
}}]}}

### Example 2: Missing Type Hints (Info - Python 3.9+)

```python
+ def get_user(user_id):
+     return db.query(User).filter_by(id=user_id).first()
```

Output: {{"findings": [{{
    "line": 1,
    "severity": "info",
    "message": "Missing type hints for function signature",
    "suggestion": "Add types: def get_user(user_id: int) -> Optional[User]:",
    "confidence": 0.85
}}]}}

### Example 3: Well-Written Code (No Issue)

```python
+ def calculate_total_price(unit_price: float, quantity: int) -> float:
+     \"\"\"Calculate total price including tax.\"\"\"
+     subtotal = unit_price * quantity
+     return subtotal * (1 + TAX_RATE)
```

Output: {{"findings": []}}

## Evaluation Criteria

- Naming conventions appropriate for {language}
- Function length and complexity (suggest splitting if > 20 lines)
- Documentation for public APIs
- Type hints where applicable
- Import organization
- Consistent coding patterns

## Rules

1. Only report confidence > 0.7
2. Only analyze NEW code (+ lines)
3. Severity: critical/warning/info/suggestion

## Output (JSON only):

{{"findings": [...]}}
"""

````

---

### 4.4 Cải Thiện FIX_PROMPT

#### Priority: 🟡 MEDIUM

```python
FIX_PROMPT_V2 = """
You are an expert code fixer generating a minimal fix for a code review issue.

## Issue Details
- **Problem**: {issue_description}
- **File**: {file_path}
- **Line**: {line}

## Code Context:
```{language}
{code_context}
````

## Your Task

Generate the MINIMAL fix for this specific issue.

## Fix Guidelines

✅ Preserve original code style and indentation
✅ Change only what's necessary to fix the issue
✅ Ensure the fix is syntactically correct
✅ Keep the fix simple and reviewable

## Examples

### Example 1: Fixing Null Check

Issue: "Potential null reference on user.name"
Context:

```python
user = get_user(user_id)
print(user.name)  # <-- issue here
```

Fix:
{{"fixed_code": "if user:\\n    print(user.name)", "explanation": "Added null check before accessing user.name"}}

### Example 2: Fixing SQL Injection

Issue: "SQL injection via string interpolation"
Context:

```python
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)
```

Fix:
{{"fixed_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))", "explanation": "Use parameterized query to prevent SQL injection"}}

### Example 3: Fixing Off-by-one

Issue: "Loop iterates beyond array bounds"
Context:

```python
for i in range(len(items) + 1):
    process(items[i])
```

Fix:
{{"fixed_code": "for i in range(len(items)):\\n    process(items[i])", "explanation": "Removed +1 to stay within array bounds"}}

## Rules

1. Output ONLY valid JSON
2. Preserve original indentation (use \\n and spaces)
3. Keep explanation to 1 sentence

## Output Format:

{{"fixed_code": "corrected code", "explanation": "brief explanation"}}
"""

````

---

### 4.5 Cải Thiện EXPLAIN_PROMPT

#### Priority: 🟢 LOW

```python
EXPLAIN_PROMPT_V2 = """
You are a senior developer explaining a code issue to a teammate who wants to learn.

## Issue Details
- **Problem**: {issue_description}
- **File**: {file_path}
- **Line**: {line}

## Code Context:
```{language}
{code_context}
````

## Your Task

Explain this issue in a way that helps the developer understand and learn.

## Explanation Structure

### 1. 🔍 What is the problem?

Clearly explain what's wrong with the code.

### 2. ⚠️ Why is it a problem?

- What could go wrong in production?
- What security/performance/reliability risks exist?
- Show a concrete scenario where this fails.

### 3. ✅ How to fix it?

- Step-by-step fix guidance
- Show the corrected code

### 4. 📚 Learn More

- Link to relevant documentation or articles (if applicable)
- Related best practices to remember

## Example Explanation

For issue: "SQL injection via string concatenation"

---

### 🔍 What is the problem?

The code builds an SQL query by directly inserting user input into the query string:

```python
query = f"SELECT * FROM users WHERE email = '{email}'"
```

### ⚠️ Why is it dangerous?

An attacker could input: `' OR '1'='1' --`

This turns your query into:

```sql
SELECT * FROM users WHERE email = '' OR '1'='1' --'
```

This would return ALL users, bypassing authentication!

### ✅ How to fix it

Use **parameterized queries** that automatically escape user input:

```python
# Before (vulnerable)
query = f"SELECT * FROM users WHERE email = '{email}'"
cursor.execute(query)

# After (safe)
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
```

### 📚 Learn More

- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)

---

## Format your response in Markdown.

"""

````

---

### 4.6 Cải Thiện GENERATE_TESTS_PROMPT

#### Priority: 🔴 HIGH

```python
GENERATE_TESTS_PROMPT_V2 = """
You are a senior test engineer creating comprehensive unit tests.

## PR Changes:
````

{pr_diff}

````

## Target: {target}

## Your Task
Generate unit tests that ensure the changed code works correctly.

## Test Requirements

### Coverage Goals
✅ Happy path - normal expected usage
✅ Edge cases - null, empty, boundary values
✅ Error cases - invalid inputs, exceptions
✅ Integration points - mock external dependencies

### Test Quality Standards
- Descriptive test names following: test_<function>_<scenario>_<expected_result>
- One assertion focus per test
- Clear Arrange-Act-Assert structure
- Docstrings explaining test purpose

## Examples

### Example 1: Testing a User Service
For code:
```python
def get_user(user_id: int) -> Optional[User]:
    if user_id <= 0:
        raise ValueError("Invalid user ID")
    return db.query(User).filter_by(id=user_id).first()
````

Generated tests:

```python
import pytest
from unittest.mock import Mock, patch
from myapp.services import get_user

class TestGetUser:
    \"\"\"Tests for the get_user function.\"\"\"

    def test_get_user_valid_id_returns_user(self):
        \"\"\"Should return user when valid ID exists.\"\"\"
        # Arrange
        mock_user = Mock(id=1, name="John")
        with patch('myapp.services.db') as mock_db:
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_user

            # Act
            result = get_user(1)

            # Assert
            assert result == mock_user

    def test_get_user_nonexistent_id_returns_none(self):
        \"\"\"Should return None when user ID doesn't exist.\"\"\"
        with patch('myapp.services.db') as mock_db:
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            result = get_user(999)

            assert result is None

    def test_get_user_zero_id_raises_error(self):
        \"\"\"Should raise ValueError for zero ID.\"\"\"
        with pytest.raises(ValueError, match="Invalid user ID"):
            get_user(0)

    def test_get_user_negative_id_raises_error(self):
        \"\"\"Should raise ValueError for negative ID.\"\"\"
        with pytest.raises(ValueError, match="Invalid user ID"):
            get_user(-1)
```

## Testing Framework

- Python: pytest with pytest-mock
- JavaScript/TypeScript: jest
- Follow existing project test patterns if visible

## Output

Generate complete, runnable test code with:

- All necessary imports
- Test class/function organization
- Comprehensive docstrings

```{language}
# Your generated tests here
```

"""

```

---

## 5. Action Items & Roadmap

### 5.1 Priority Matrix

| Action | Effort | Impact | Priority |
|--------|--------|--------|----------|
| Add Few-shot examples to all prompts | Medium | 🔴 High | P0 |
| Add CoT reasoning to Logic/Security | Low | 🔴 High | P0 |
| Replace negative instructions | Low | 🟡 Medium | P1 |
| Add framework/language context | Medium | 🟡 Medium | P1 |
| Create prompt versioning system | Medium | 🟢 Low | P2 |
| Add prompt A/B testing | High | 🟢 Low | P2 |

### 5.2 Implementation Phases

#### Phase 1: Quick Wins (1-2 days)
- [ ] Add 2-3 examples to each agent prompt
- [ ] Add "Let's think step by step" to Logic and Security prompts
- [ ] Replace "Don't be pedantic" with positive instructions

#### Phase 2: Enhanced Prompts (3-5 days)
- [ ] Implement full V2 prompts as shown above
- [ ] Add framework/language-specific variations
- [ ] Add dynamic context injection (project conventions)

#### Phase 3: Advanced Techniques (1-2 weeks)
- [ ] Implement prompt templates with Jinja2
- [ ] Add prompt versioning and rollback
- [ ] Create evaluation framework for prompt quality
- [ ] Consider Tree-of-Thoughts for complex security analysis

### 5.3 Metrics to Track

| Metric | Current Baseline | Target |
|--------|-----------------|--------|
| False Positive Rate | ? | < 10% |
| Output Format Errors | ? | < 2% |
| User-reported missed issues | ? | < 5% |
| Average confidence score | ? | > 0.80 |

---

## 6. Tài Liệu Tham Khảo

### Official Sources
- [Prompt Engineering Guide](https://www.promptingguide.ai/) - Primary reference
- [OpenAI Best Practices](https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-openai-api)

### Key Techniques
- [Zero-Shot Prompting](https://www.promptingguide.ai/techniques/zeroshot)
- [Few-Shot Prompting](https://www.promptingguide.ai/techniques/fewshot)
- [Chain-of-Thought Prompting](https://www.promptingguide.ai/techniques/cot)
- [Tree of Thoughts](https://www.promptingguide.ai/techniques/tot)

### Research Papers
- Wei et al., 2022 - Chain-of-Thought Prompting
- Kojima et al., 2022 - Zero-shot CoT ("Let's think step by step")
- Yao et al., 2023 - Tree of Thoughts
- Brown et al., 2020 - Few-shot Learning

### Code Review Specific
- [Generating Code](https://www.promptingguide.ai/applications/coding) - Code generation prompts

---

## 📝 Notes

### Về Việc Sử Dụng Structured Output (Pydantic)

Nếu đang sử dụng `llm.with_structured_output()` với Pydantic models, một số cải thiện prompt có thể không cần thiết vì model đã bị constrain output format. Tuy nhiên:

- **Vẫn cần Few-shot**: Để model hiểu _content_ mong muốn, không chỉ format
- **Vẫn cần CoT**: Để cải thiện chất lượng reasoning trước khi output
- **Examples trong prompt vẫn hữu ích**: Chúng hướng dẫn model về semantic, không chỉ syntax

### Về Token Cost

Prompts cải thiện sẽ dài hơn (~2-3x). Cân nhắc:
- Cache prompts nếu có thể
- Sử dụng smaller examples cho common cases
- Consider prompt compression techniques

---

*Document version: 1.0*
*Last updated: 2025-12-29*
```
