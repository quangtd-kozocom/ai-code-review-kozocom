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

Generate search queries that will find ALL callers/usages of this entity.

### Language-Specific Patterns:

**PHP:**
- Function calls: `functionName(`
- Static method: `ClassName::methodName(`
- Instance method: `->methodName(`

**TypeScript/JavaScript:**
- Function calls: `functionName(`
- Method calls: `.methodName(`

**Python:**
- Function calls: `function_name(`
- Method calls: `.method_name(`

**Go:**
- Function calls: `functionName(`
- Method calls: `.MethodName(`

### Guidelines:
1. Use simple, literal text queries (NO regex escaping, NO backslashes)
2. Include multiple patterns for different call styles
3. Exclude test files, vendor directories

## Output

Provide:
1. Search queries as PLAIN TEXT (e.g., `processPayment(` not `processPayment\\(`)
2. File patterns to include
3. File patterns to exclude
4. Brief reasoning
"""
