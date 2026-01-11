"""Prompt for generating review comments with multi-language support."""

from ..locales import get_locale

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

Generate a clear, actionable review comment using EXACTLY this format with these labels:

```
🚨 **{label_breaking_change}**

**{label_problem}:** [Describe what changed and list ALL affected files with line numbers]

**{label_context_used}:**
🔗 {label_dependencies} (N {label_analyzed}):
- [list relevant dependencies]

📁 {label_external_files} (N {label_affected}):
| {label_file} | {label_break_reason} |
|------|--------------|
| path/to/file.php | [specific reason] |

**{label_recommendation}:** [Specific actionable fix]
```

### Key Requirements:
1. Use the EXACT labels provided above (they are already translated)
2. **{label_problem}** must clearly state what changed and list ALL affected files
3. **{label_recommendation}** must be specific and actionable
4. Write all descriptive content in {language_name}

### Severity:
- **critical**: Runtime errors, crashes, data loss (3+ affected files)
- **warning**: May cause issues (1-2 affected files)
- **info**: Minor concern

## Output

Generate the comment with the exact structure and labels shown above.
"""

LANGUAGE_NAMES = {
    "en": "English",
    "vi": "Vietnamese (Tiếng Việt)",
    "ja": "Japanese (日本語)",
    "zh": "Chinese (中文)",
}


def get_generate_review_prompt(output_language: str = "en") -> str:
    """Get the generate review prompt with localized labels."""
    labels = get_locale(output_language)
    lang_name = LANGUAGE_NAMES.get(output_language, "English")
    
    return GENERATE_REVIEW_PROMPT.format(
        file_path="{file_path}",
        entity_name="{entity_name}",
        entity_type="{entity_type}",
        change_type="{change_type}",
        change_detail="{change_detail}",
        old_definition="{old_definition}",
        new_definition="{new_definition}",
        affected_callers="{affected_callers}",
        label_breaking_change=labels["breaking_change"],
        label_problem=labels["problem"],
        label_context_used=labels["context_used"],
        label_dependencies=labels["dependencies"],
        label_analyzed=labels["analyzed"],
        label_external_files=labels["external_files"],
        label_affected=labels["affected"],
        label_file=labels["file"],
        label_break_reason=labels["break_reason"],
        label_recommendation=labels["recommendation"],
        language_name=lang_name,
    )
