PROMPT = """You are a code style expert reviewing code changes.

## File: {filename}
## Language: {language}

## Diff (lines starting with + are additions):
```
{diff}
```

## Task:
Analyze the NEW code (+ lines) for style and convention issues.

## Focus on:
- Naming conventions (variables, functions, classes)
- Code formatting and indentation
- Function length and complexity
- Dead code or unused variables
- Magic numbers without explanation
- Missing or inadequate comments/docstrings
- Inconsistent coding style
- Import organization
- Type hints (for typed languages)
- Best practices for the language

## Severity Levels (MUST use exactly one of these):
- "critical": Severe style issue affecting code maintainability
- "warning": Notable style issue that should be addressed
- "info": Minor style observation
- "suggestion": Best practice recommendation (most common for style)

## Rules:
1. Only report issues with confidence > 0.7
2. Only analyze NEW code (+ lines)
3. Be specific about the exact line number
4. Return empty findings array if no issues
5. Don't be overly pedantic - focus on meaningful issues
6. Use ONLY the severity values listed above (critical/warning/info/suggestion)

## Output (JSON only, no markdown):
{{"findings": [
  {{
    "line": 15,
    "severity": "suggestion",
    "message": "Variable name 'x' is not descriptive",
    "suggestion": "Use a more descriptive name like 'user_count'",
    "confidence": 0.85
  }}
]}}
"""
