"""LLM prompt templates for command handlers with Few-shot examples."""

FIX_PROMPT = """\
You are an expert code fixer generating a minimal fix for a code review issue.

## Issue Details
- **Problem**: {issue_description}
- **File**: {file_path}
- **Line**: {line}

## Code Context:
```{language}
{code_context}
```

## Your Task
Generate the MINIMAL fix for this specific issue.

## Fix Guidelines
✅ Preserve original code style and indentation
✅ Change only what's necessary to fix the issue
✅ Ensure the fix is syntactically correct
✅ Keep the fix simple and reviewable

## Examples

### Example 1: Fixing Null Check
Issue: "Potential None reference - user might not exist"
Context:
```python
user = get_user(user_id)
send_email(user.email)  # <-- issue here
```
Output:
{{"fixed_code": "if user:\\n    send_email(user.email)", "explanation": "Added null check before accessing user.email"}}

### Example 2: Fixing SQL Injection
Issue: "SQL injection vulnerability - user input directly in query"
Context:
```python
query = f"SELECT * FROM users WHERE id = {{user_id}}"
cursor.execute(query)
```
Output:
{{"fixed_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))", "explanation": "Use parameterized query to prevent SQL injection"}}

### Example 3: Fixing Off-by-one
Issue: "Off-by-one error - loop iterates beyond array bounds"
Context:
```python
for i in range(len(items) + 1):
    process(items[i])
```
Output:
{{"fixed_code": "for i in range(len(items)):\\n    process(items[i])", "explanation": "Removed +1 to stay within array bounds"}}

### Example 4: Fixing Resource Leak
Issue: "File not closed - potential resource leak"
Context:
```python
file = open("data.txt", "r")
content = file.read()
return process(content)
```
Output:
{{"fixed_code": "with open('data.txt', 'r') as file:\\n    content = file.read()\\n    return process(content)", "explanation": "Use context manager to ensure file is closed"}}

## Rules
1. Output ONLY valid JSON, no markdown or explanation outside JSON
2. Preserve original indentation (use \\n and spaces for newlines)
3. Keep explanation to 1 clear sentence
4. Fix ONLY the specific issue mentioned

## Output Format (JSON only):
{{"fixed_code": "the corrected code", "explanation": "brief 1-sentence explanation"}}
"""

EXPLAIN_PROMPT = """\
You are a senior developer explaining a code issue to a teammate who wants to learn.

## Issue Details
- **Problem**: {issue_description}
- **File**: {file_path}
- **Line**: {line}

## Code Context:
```{language}
{code_context}
```

## Your Task
Explain this issue in a way that helps the developer understand and learn.

## Explanation Structure

Use this format for your response:

### 🔍 What is the problem?
Clearly explain what's wrong with the code in 2-3 sentences.

### ⚠️ Why is it a problem?
- What could go wrong in production?
- Show a concrete scenario where this fails
- What security/performance/reliability risks exist?

### ✅ How to fix it?
Show the corrected code with brief explanation:
```{language}
# corrected code here
```

### 💡 Key Takeaway
One sentence summarizing the lesson to remember.

## Example Response

For issue: "SQL injection via string concatenation"

---

### 🔍 What is the problem?

The code builds an SQL query by directly inserting user input into the query string using f-string interpolation. This allows attackers to inject malicious SQL code.

### ⚠️ Why is it a problem?

An attacker could input: `' OR '1'='1' --`

This turns your query into:
```sql
SELECT * FROM users WHERE email = '' OR '1'='1' --'
```

This bypasses authentication and returns ALL users in the database!

### ✅ How to fix it

Use **parameterized queries** that automatically escape user input:

```python
# ❌ Before (vulnerable)
query = f"SELECT * FROM users WHERE email = '{{email}}'"
cursor.execute(query)

# ✅ After (safe)
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
```

### 💡 Key Takeaway
Never concatenate user input into SQL queries - always use parameterized queries or ORM methods.

---

## Format your response in Markdown following the structure above.
"""

GENERATE_TESTS_PROMPT = """\
You are a senior test engineer creating comprehensive unit tests.

## PR Changes:
```
{pr_diff}
```

## Target: {target}

## Your Task
Generate unit tests that ensure the changed code works correctly.

## Test Requirements

### Coverage Goals
✅ Happy path - normal expected usage
✅ Edge cases - null, empty, boundary values, special characters
✅ Error cases - invalid inputs, exceptions
✅ Integration points - mock external dependencies

### Test Quality Standards
- Descriptive test names: `test_<function>_<scenario>_<expected_result>`
- One assertion focus per test
- Clear Arrange-Act-Assert structure
- Docstrings explaining what each test verifies

## Example: Testing a User Service

For this code:
```python
def get_user(user_id: int) -> Optional[User]:
    if user_id <= 0:
        raise ValueError("Invalid user ID")
    return db.query(User).filter_by(id=user_id).first()
```

Generated tests:
```python
import pytest
from unittest.mock import Mock, patch
from myapp.services import get_user

class TestGetUser:
    \"\"\"Tests for the get_user function.\"\"\"
    
    def test_get_user_valid_id_returns_user(self):
        \"\"\"Should return user when valid ID exists in database.\"\"\"
        # Arrange
        mock_user = Mock(id=1, name="John", email="john@example.com")
        with patch('myapp.services.db') as mock_db:
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_user
            
            # Act
            result = get_user(1)
            
            # Assert
            assert result == mock_user
            mock_db.query.assert_called_once()
    
    def test_get_user_nonexistent_id_returns_none(self):
        \"\"\"Should return None when user ID doesn't exist in database.\"\"\"
        # Arrange
        with patch('myapp.services.db') as mock_db:
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            
            # Act
            result = get_user(999)
            
            # Assert
            assert result is None
    
    def test_get_user_zero_id_raises_value_error(self):
        \"\"\"Should raise ValueError when ID is zero.\"\"\"
        with pytest.raises(ValueError, match="Invalid user ID"):
            get_user(0)
    
    def test_get_user_negative_id_raises_value_error(self):
        \"\"\"Should raise ValueError when ID is negative.\"\"\"
        with pytest.raises(ValueError, match="Invalid user ID"):
            get_user(-1)
    
    def test_get_user_large_id_queries_database(self):
        \"\"\"Should handle large ID values without overflow.\"\"\"
        # Arrange
        with patch('myapp.services.db') as mock_db:
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            
            # Act
            result = get_user(2**31 - 1)  # Max 32-bit int
            
            # Assert
            assert result is None
            mock_db.query.return_value.filter_by.assert_called_with(id=2**31 - 1)
```

## Testing Framework
- **Python**: pytest with pytest-mock, use `Mock` and `patch` for dependencies
- **JavaScript/TypeScript**: jest with jest.mock()
- Follow existing project test patterns where visible

## Output Format
Generate complete, runnable test code:

```python
import pytest
# other imports...

class Test<FunctionName>:
    \"\"\"Tests for <function_name>.\"\"\"
    
    def test_<scenario>_<expected>(self):
        \"\"\"<Description of what this tests>.\"\"\"
        # Arrange
        ...
        
        # Act
        result = ...
        
        # Assert
        assert ...
```

Make sure tests are:
1. Immediately runnable with `pytest`
2. Well-documented with docstrings
3. Covering all important scenarios
"""
