"""Prompt for planning search queries."""

PLAN_SEARCH_PROMPT = """You need to find all usages of a changed code entity across the codebase.

## Change Information
- Entity Type: {entity_type}
- Entity Name: {entity_name}
- Class Name: {class_name}
- Language: {language}
- File: {file_path}
- Change Type: {change_type}
- Change Detail: {change_detail}

## Old Definition:
```
{old_definition}
```

## New Definition:
```
{new_definition}
```

## Your Task

Generate search queries (simple text patterns) to find ALL callers/usages of this entity.

### Examples of GOOD queries:
- `processPayment(`
- `->methodName(`
- `ClassName::methodName(`
- `STATUS_PENDING`

### Examples of BAD queries (DO NOT USE):
- `grep -r ...` (NO shell commands!)
- `processPayment\\(` (NO escaping!)
- `.*processPayment.*` (NO regex!)

### Guidelines:
1. Return ONLY simple text strings to search for
2. Include the opening parenthesis for function/method calls
3. Include multiple patterns for different call styles

## Output

Provide:
1. queries: List of simple text strings (NOT shell commands, NOT regex)
2. include_patterns: File glob patterns like `*.php`
3. exclude_patterns: Patterns to exclude like `*Test.php`, `vendor/*`
4. reasoning: Brief explanation
"""
