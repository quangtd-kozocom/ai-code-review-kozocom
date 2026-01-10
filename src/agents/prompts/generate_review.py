"""Prompt for generating review comments."""

GENERATE_REVIEW_PROMPT = """You are generating a code review comment for a breaking change.

## Breaking Change Details

- File: {file_path}
- Entity: {entity_name} ({entity_type})
- Change Type: {change_type}
- Change Detail: {change_detail}

### Old Definition:
```
{old_definition}
```

### New Definition:
```
{new_definition}
```

## Affected Callers

{affected_callers}

## Your Task

Generate a clear, actionable review comment using this format:

```
🚨 **Breaking Change Detected**

**Problem:** [Describe what changed and list ALL affected files with line numbers]

**Context Used:**
🔗 Dependencies (N analyzed):
- [list relevant dependencies]

📁 External Files (N affected):
| File | Break Reason |
|------|--------------|
| path/to/file.php | [specific reason] |

**Recommendation:** [Specific actionable fix]
```

### Key Requirements:
1. **Problem** must clearly state what changed and list ALL affected files with line numbers
2. **Context Used** shows dependencies analyzed and affected files in a table
3. **Recommendation** must be specific and actionable

### Severity:
- **critical**: Runtime errors, crashes, data loss (3+ affected files)
- **warning**: May cause issues (1-2 affected files)
- **info**: Minor concern

## Output

Generate the comment with the exact structure shown above.
"""
