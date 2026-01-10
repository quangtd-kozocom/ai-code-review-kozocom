"""Prompts for context evaluation and enrichment loop."""

EVALUATE_CONTEXT_PROMPT = """You are evaluating if we have enough context to accurately review a Pull Request.

## Changed Code:
{changed_code}

## External Files Found (files that USE the changed code):
{external_files}

## Your Task:
Determine if we have sufficient context to identify all files that will be affected by these changes.

### Questions to Consider:
1. Do we have ENOUGH context to identify all files that will break?
2. Are there any dependencies we should search for but haven't found yet?
3. What additional classes or services would help complete the picture?

### Examples of Missing Context:
- If PaymentService changed, we should also check for OrderService that might use it
- If a Model changed, we should check for Controllers, Jobs, and Listeners
- If an exception type changed, we should find all catch blocks

## Return Format:
Provide a structured evaluation with:
- context_sufficient: true if we have enough, false if we need more
- need_more_context_for: list of class/service names to search for next
- confidence: how confident you are (0.0 to 1.0)
- reasoning: explain your decision

Be conservative - if unsure, request more context.
"""


def format_changed_code(function_changes: dict[str, dict]) -> str:
    """Format function changes for the prompt."""
    lines = []
    
    for func_name, change_info in function_changes.items():
        change_type = change_info.get("type", "modified")
        old_func = change_info.get("old")
        new_func = change_info.get("new")
        
        lines.append(f"### Function: {func_name}")
        lines.append(f"**Change Type:** {change_type}")
        
        if old_func:
            lines.append(f"**Old Signature:** `{old_func.signature}`")
        
        if new_func:
            lines.append(f"**New Signature:** `{new_func.signature}`")
            lines.append(f"**File:** {new_func.file_path}")
        
        lines.append("")
    
    return "\n".join(lines)


def format_external_files(external_files: list) -> str:
    """Format external files for the prompt."""
    if not external_files:
        return "No external files found yet."
    
    lines = []
    
    for ext_file in external_files:
        lines.append(f"### {ext_file.path}")
        lines.append(f"**Usage Type:** {ext_file.usage_type}")
        lines.append(f"**References:** {', '.join(ext_file.references)}")
        
        if ext_file.will_break:
            lines.append(f"**⚠️ Will Break:** {ext_file.break_reason}")
        
        lines.append("")
    
    return "\n".join(lines)
