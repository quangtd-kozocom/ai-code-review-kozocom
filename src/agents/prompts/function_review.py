"""Function review prompts for targeted LLM review.

Provides structured prompts for reviewing individual functions
with precise context and targeted questions.
"""

SYSTEM_PROMPT = """You are an expert code reviewer focusing on code quality, security, and correctness.

## 🛡️ ANTI-HALLUCINATION PROTOCOL

Before reporting ANY issue:
1. **CITE YOUR SOURCE**: Quote exact code from provided context proving the issue
2. **VERIFY DON'T SPECULATE**: If you can't cite proof, DON'T report it
3. **ADMIT UNCERTAINTY**: If implementation not in context, say so explicitly

## Your Approach
- Be specific and actionable in your feedback
- Prioritize critical issues over style preferences
- Consider the context of callers and callees
- Suggest concrete improvements when possible

## Output Format
Respond with a JSON object containing a "findings" array.
Each finding must have:
- line: int (the line number in the new code)
- severity: "critical" | "warning" | "info" | "suggestion"
- message: str (clear explanation of the issue)
- suggestion: str | null (how to fix it)
- confidence: float (0.0 to 1.0, how certain you are)
"""


def build_function_review_prompt(
    function_name: str,
    file_path: str,
    change_type: str,
    impact_level: str,
    old_code: str | None,
    new_code: str | None,
    diff: str | None,
    callers: list[dict],
    callees: list[str],
    review_questions: list[str],
    focus_areas: list[str],
    review_depth: str,
) -> str:
    """Build targeted prompt for function review.
    
    Args:
        function_name: Name of the function being reviewed.
        file_path: Path to the file.
        change_type: Type of change (added, modified, deleted).
        impact_level: Impact level from analysis.
        old_code: Previous version of the code.
        new_code: New version of the code.
        diff: Unified diff of changes.
        callers: List of functions that call this one.
        callees: List of functions this one calls.
        review_questions: Specific questions to answer.
        focus_areas: Areas to focus on during review.
        review_depth: How deep to review (deep, standard, quick).
        
    Returns:
        Formatted prompt string.
    """
    lines = [
        f"# Review: `{function_name}`",
        "",
        f"**File**: {file_path}",
        f"**Change Type**: {change_type.upper()}",
        f"**Impact Level**: {impact_level.upper()}",
        f"**Review Depth**: {review_depth}",
        "",
    ]
    
    # Focus areas
    if focus_areas:
        lines.extend([
            "## Focus Areas",
            "",
        ])
        for area in focus_areas:
            match area:
                case "backward_compatibility":
                    lines.append("- ⚠️ **Backward Compatibility**: Check if changes break existing callers")
                case "caller_impact":
                    lines.append("- 📞 **Caller Impact**: Verify callers will work correctly")
                case "test_coverage":
                    lines.append("- 🧪 **Test Coverage**: This function lacks tests")
                case "breaking_changes":
                    lines.append("- 🔴 **Breaking Changes**: Signature or behavior changes detected")
                case "api_stability":
                    lines.append("- 📊 **API Stability**: Many callers depend on this")
                case _:
                    lines.append(f"- {area}")
        lines.append("")
    
    # Code changes
    if old_code and change_type != "added":
        lines.extend([
            "## Before",
            "```python",
            old_code.strip(),
            "```",
            "",
        ])
    
    if new_code and change_type != "deleted":
        lines.extend([
            "## After",
            "```python",
            new_code.strip(),
            "```",
            "",
        ])
    
    if diff:
        lines.extend([
            "## Diff",
            "```diff",
            diff.strip(),
            "```",
            "",
        ])
    
    # Callers context
    if callers:
        lines.extend([
            f"## Callers ({len(callers)} functions call this)",
            "",
        ])
        for caller in callers[:5]:
            lines.extend([
                f"### `{caller['name']}` in {caller['file']}:{caller.get('line', '?')}",
                "```python",
                caller.get("context", "# Context not available"),
                "```",
                "",
            ])
    
    # Callees
    if callees:
        lines.extend([
            f"## Dependencies (calls {len(callees)} functions)",
            "",
            ", ".join(f"`{c}`" for c in callees[:10]),
            "",
        ])
    
    # Review questions
    if review_questions:
        lines.extend([
            "## Specific Questions",
            "",
        ])
        for i, q in enumerate(review_questions, 1):
            lines.append(f"{i}. {q}")
        lines.append("")
    
    # Review instructions based on depth
    match review_depth:
        case "deep":
            lines.extend([
                "## Review Instructions (DEEP)",
                "",
                "Perform a thorough review covering:",
                "- Logic correctness and edge cases",
                "- Security implications",
                "- Error handling completeness",
                "- Performance considerations",
                "- Impact on all callers",
                "- API contract changes",
                "",
            ])
        case "standard":
            lines.extend([
                "## Review Instructions (STANDARD)",
                "",
                "Focus on:",
                "- Logic correctness",
                "- Obvious bugs or issues",
                "- Error handling",
                "- Direct caller impact",
                "",
            ])
        case "quick":
            lines.extend([
                "## Review Instructions (QUICK)",
                "",
                "Quick check for:",
                "- Obvious bugs",
                "- Critical security issues",
                "",
            ])
    
    lines.extend([
        "Respond with JSON only. Format:",
        '{"findings": [{"line": N, "severity": "...", "message": "...", "suggestion": "...", "confidence": 0.X}]}',
    ])
    
    return "\n".join(lines)


DEEP_REVIEW_CRITERIA = """
## Deep Review Checklist

### Logic & Correctness
- [ ] Are all code paths handled correctly?
- [ ] Are edge cases (null, empty, boundary) handled?
- [ ] Is the algorithm/logic correct?

### Security
- [ ] Is user input validated/sanitized?
- [ ] Are there SQL injection risks?
- [ ] Are secrets properly handled?
- [ ] Is authorization checked?

### Error Handling
- [ ] Are exceptions caught appropriately?
- [ ] Are errors logged with context?
- [ ] Is cleanup done in finally blocks?

### Performance
- [ ] Are there N+1 query patterns?
- [ ] Is there unnecessary iteration?
- [ ] Are resources properly closed?

### API Contract
- [ ] Is the signature backward compatible?
- [ ] Are return values consistent?
- [ ] Is documentation accurate?
"""
