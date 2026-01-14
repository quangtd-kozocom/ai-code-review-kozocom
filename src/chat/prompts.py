"""LLM prompt templates for command handlers."""

# Enhanced fix prompt with full context support
FIX_PROMPT = """\
You are an expert code fixer. Generate minimal, precise fixes for breaking changes.

## Breaking Change
- **Entity**: {entity_name}
- **Change**: {change_detail}
- **Source File**: {source_file}

## Affected File to Fix
- **Path**: {file_path}
- **Line**: {line}
- **Reason**: {break_reason}

## Current Code Context:
```{language}
{code_context}
```

## Output Requirements
- `fixed_code`: Show ONLY the changed lines in unified diff format (- for old, + for new)
- `explanation`: One sentence describing the fix
- Do NOT include the entire file, only the specific lines that changed

Example output format:
```json
{{
  "fixed_code": "-    'status' => Order::STATUS_PENDING,\\n+    'status' => Order::STATUS_AWAITING_PAYMENT,",
  "explanation": "Replaced deprecated STATUS_PENDING with STATUS_AWAITING_PAYMENT"
}}
```

Output JSON only:
"""

# Fallback prompt when no breaking change context available
FIX_PROMPT_SIMPLE = """\
You are an expert code fixer generating a minimal fix for a code review issue.

## Issue Details
- **Problem**: {issue_description}
- **File**: {file_path}
- **Line**: {line}

## Code Context:
```{language}
{code_context}
```

## Output Requirements
- `fixed_code`: Show ONLY the changed lines in unified diff format (- for old, + for new)
- `explanation`: One sentence describing the fix
- Do NOT include the entire file, only the specific lines that changed

Output JSON only:
"""

# Multi-file fix prompt
FIX_PROMPT_BATCH = """\
You are an expert code fixer. Generate fixes for ALL affected files due to a breaking change.

## Breaking Change
- **Entity**: {entity_name}
- **Change**: {change_detail}
- **Source File**: {source_file}

## Affected Files ({file_count} files):
{files_context}

## Fix Guidelines
1. Update each file to use the new API/constant/method
2. Preserve original code style
3. Output fixes for ALL files

Output JSON array: [{{"file": "path", "fixed_code": "...", "explanation": "..."}}]
"""
