# 📝 Generate Docstrings

> Tự động generate docstrings cho functions/classes trong PR

**Độ ưu tiên:** 🔴 Cao  
**Độ phức tạp:** Thấp  
**Tham khảo:** [CodeRabbit Docstrings](https://docs.coderabbit.ai/finishing-touches/docstrings)

---

## 📋 Mô Tả

Cho phép developer yêu cầu AI tự động generate docstrings cho:

1. Functions thiếu documentation
2. Classes và methods
3. Module-level docstrings
4. Follow coding conventions của team (Google, NumPy, Sphinx, etc.)

---

## 🎯 Mục Tiêu

- **Primary:** Cải thiện code documentation tự động
- **Secondary:** Enforce consistent docstring format
- **Tertiary:** Giảm thời gian viết documentation

---

## 💡 Command Usage

```markdown
# Generate docstrings for all functions in PR

@reviewer docstrings

# Generate for specific file

@reviewer docstrings for auth.py

# Generate with specific style

@reviewer docstrings --style google
```

### Example Output

```markdown
## 📝 Generated Docstrings

I've generated documentation for **3 functions** in this PR:

### `src/auth/validator.py`

\`\`\`suggestion
def validate_email(email: str) -> bool:
"""Validate email address format.

    Args:
        email: The email address string to validate.

    Returns:
        True if the email format is valid, False otherwise.

    Raises:
        ValueError: If email is None or empty string.

    Example:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid-email")
        False
    """

\`\`\`

---

_Click "Commit suggestion" to apply, or ask for modifications._
```

---

## 🛠️ Technical Implementation

### 1. Add Command Type

```python
# src/chat/commands.py

class CommandType(StrEnum):
    FIX = "fix"
    GENERATE_TESTS = "generate_tests"
    EXPLAIN = "explain"
    HELP = "help"
    DOCSTRINGS = "docstrings"  # NEW
    UNKNOWN = "unknown"
```

### 2. Add Parser Pattern

```python
# src/chat/parser.py

_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    # ... existing patterns ...
    CommandType.DOCSTRINGS: re.compile(
        r"@reviewer\s+docstrings?(?:\s+(?:for\s+)?(.+))?",
        re.IGNORECASE
    ),
}
```

### 3. Create Handler

```python
# src/chat/handler.py

class DocstringsCommandHandler(BaseCommandHandler):
    """Generate docstrings for functions in PR."""

    async def execute(self, ctx: CommandContext) -> str:
        try:
            pr_files = await self.github.get_pr_files(
                ctx.owner, ctx.repo, ctx.pr_number
            )

            # Filter to target files
            target_files = self._filter_files(pr_files, ctx.target)

            if not target_files:
                return "❌ No Python/JS files found in PR."

            docstrings = []
            for file in target_files[:3]:  # Limit
                prompt = DOCSTRINGS_PROMPT.format(
                    filename=file["filename"],
                    code=file["patch"],
                    style=ctx.options.get("style", "google"),
                )
                response = await self.llm.ainvoke(prompt)
                docstrings.append({
                    "file": file["filename"],
                    "content": response.content,
                })

            return self._format_response(docstrings)

        except Exception as e:
            log.exception("Docstring generation failed")
            return f"❌ Error: {e}"
```

### 4. Prompt Template

```python
# src/chat/prompts.py

DOCSTRINGS_PROMPT = """You are a documentation expert.

## Task
Generate comprehensive docstrings for the following code changes.

## File: {filename}

```

{code}

````

## Requirements
1. Use {style} docstring format
2. Include:
   - Brief description
   - Args with types and descriptions
   - Returns with type and description
   - Raises if applicable
   - Example usage for public functions
3. Be concise but complete
4. Match existing code style

## Output Format
For each function, output in GitHub suggestion format:

```suggestion
def function_name(...):
    \"\"\"Docstring here.\"\"\"
````

Only include the function signature and docstring, not the body.
"""

````

---

## ⚙️ Configuration Support

Support team-specific docstring conventions via `.reviewer.yaml`:

```yaml
# .reviewer.yaml
docstrings:
  style: google  # google, numpy, sphinx, epytext
  include_examples: true
  include_raises: true
  path_instructions:
    - path: "src/api/**/*.py"
      instructions: "Include API endpoint info and response format"
    - path: "src/models/**/*.py"
      instructions: "Document fields and relationships"
````

---

## ✅ Acceptance Criteria

1. [ ] `@reviewer docstrings` generates docs for all functions
2. [ ] `@reviewer docstrings for <file>` targets specific file
3. [ ] Supports Google, NumPy, Sphinx formats
4. [ ] Output uses GitHub suggestion syntax
5. [ ] Respects existing docstring style in codebase

---

## 📊 Metrics

| Metric                      | Target |
| --------------------------- | ------ |
| Functions documented per PR | 5-10   |
| Docstring quality score     | > 80%  |
| Style consistency           | 100%   |

---

## 🔮 Future Enhancements

1. **Auto-detect style:** Analyze existing docstrings in repo
2. **Batch commit:** Apply all docstrings in one commit
3. **Type hints:** Also suggest type hints for untyped functions
4. **Multiple languages:** JavaScript/TypeScript JSDoc support
