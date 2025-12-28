"""LLM prompt templates for command handlers."""

FIX_PROMPT = """\
You are an expert code fixer.

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

EXPLAIN_PROMPT = """\
You are a senior software engineer explaining a code issue to a junior developer.

## Issue from Code Review:
{issue_description}

## File: {file_path}
## Line: {line}

## Code Context:
```{language}
{code_context}
```

## Task:
Explain this issue in detail. Be educational and helpful.

## Include:
1. **What is the problem?** - Explain the issue clearly
2. **Why is it a problem?** - What could go wrong?
3. **How to fix it?** - Step by step guidance
4. **Example** - Show correct code if helpful

## Format your response in Markdown.
"""

GENERATE_TESTS_PROMPT = """\
You are an expert test engineer.

## PR Changes:
{pr_diff}

## Target: {target}

## Task:
Generate comprehensive unit tests for the code changes.

## Testing Framework: pytest (for Python), jest (for JS/TS)

## Requirements:
1. Cover happy path scenarios
2. Cover edge cases (null, empty, boundary values)
3. Cover error scenarios
4. Use descriptive test names
5. Include docstrings explaining each test

## Output Format:
```python
import pytest

def test_...():
    \"\"\"Test description.\"\"\"
    ...
```
"""
