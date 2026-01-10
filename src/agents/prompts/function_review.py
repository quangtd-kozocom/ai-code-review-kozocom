"""Function review prompts for targeted LLM review.

Provides structured prompts for reviewing individual functions
with precise context and targeted questions.
"""

SYSTEM_PROMPT = """You are an expert code reviewer focusing on code quality, security, and correctness.

## 🛡️ ANTI-HALLUCINATION PROTOCOL

Before reporting ANY issue:
1. **CITE YOUR SOURCE**: Quote exact code from provided context proving the issue
2. **VERIFY DON'T SPECULATE**: If you can't cite proof, DON'T report it
3. **CHECK DEPENDENCIES**: If callee source is provided, verify behavior before claiming issues
4. **ADMIT UNCERTAINTY**: If implementation not in context, say so explicitly

## 🔍 DEPENDENCY VERIFICATION RULES

When you see a callee (called function):
1. **If callee source code is provided**:
   - Check if it validates inputs → DON'T report missing validation in caller
   - Check if it handles None → DON'T report None handling in caller
   - Check if it provides the safety check → DON'T duplicate the comment
   - Quote the callee code that provides the safety
2. **If callee source NOT provided**:
   - Say "Cannot verify X behavior - callee source not in context"
   - Set confidence to 0.65 (will be filtered out)
   - Do NOT assume the callee has bugs

## 📊 CONFIDENCE CALIBRATION

Use these confidence scores:
- **0.95**: Definite bug with proof (IndexError, null deref with no check, logic error)
- **0.85**: High-likelihood bug with context evidence
- **0.75**: Potential bug, callee verified
- **0.65**: Potential bug, callee NOT verified (will be filtered - below 0.7 threshold)
- **< 0.7**: Don't report - will be filtered out

## 🎯 PRIORITIZATION

**Focus on REAL BUGS:**
- Logic errors
- Unhandled exceptions
- Boundary conditions
- Security vulnerabilities
- Null/None dereferences with no safety checks

**Skip redundant validation comments:**
- If validation exists in called functions, don't report it in caller
- Aggregate related issues instead of repeating the same pattern

## Output Format
Respond with a JSON object containing a "findings" array.
Each finding must have:
- line: int (the line number in the new code)
- severity: "critical" | "warning" | "info" | "suggestion"
- message: str (clear explanation of the issue)
- suggestion: str | null (how to fix it)
- confidence: float (0.0 to 1.0, use calibration above)
- dependencies_checked: list[dict] | null (dependencies that were verified, optional)
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
    callees: list[dict],  # Changed from list[str] to list[dict] for CalleeInfo
    review_questions: list[str],
    focus_areas: list[str],
    review_depth: str,
    external_files: list[dict] | None = None,
    breaking_changes: list[str] | None = None,
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
        callees: List of CalleeInfo dicts with source code.
        review_questions: Specific questions to answer.
        focus_areas: Areas to focus on during review.
        review_depth: How deep to review (deep, standard, quick).
        external_files: External files that depend on this code (from discovery).
        breaking_changes: List of detected breaking changes.

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
    
    # Callees with source code
    if callees:
        lines.extend([
            f"## Dependencies (calls {len(callees)} functions)",
            "",
        ])

        for callee in callees:
            lines.append(f"### `{callee['name']}`")

            if callee.get('file_path'):
                lines.append(f"**File**: {callee['file_path']}")

            if callee.get('signature'):
                lines.append(f"**Signature**: `{callee['signature']}`")

            if callee.get('has_validation'):
                lines.append("**Has Validation**: ✅ Yes")

            if callee.get('returns_optional'):
                lines.append("**Can Return None**: ⚠️ Yes")

            if callee.get('source_code'):
                lines.extend([
                    "",
                    "**Source Code:**",
                    "```python",
                    callee['source_code'],
                    "```",
                ])
            else:
                lines.extend([
                    "",
                    "*Source code not available in context - cannot verify behavior*",
                ])

            lines.append("")
    
    # External files context (NEW)
    if external_files:
        lines.extend([
            f"## 🔍 External Files Affected ({len(external_files)} files found)",
            "",
            "**These files outside the PR depend on this code:**",
            "",
        ])
        
        for ext_file in external_files[:10]:  # Limit to 10
            lines.append(f"### {ext_file.get('path', 'Unknown')}")
            lines.append(f"**Usage Type:** {ext_file.get('usage_type', 'unknown')}")
            
            if ext_file.get('references'):
                lines.append(f"**References:** {', '.join(ext_file['references'])}")
            
            if ext_file.get('will_break'):
                lines.append(f"**⚠️ WILL BREAK:** {ext_file.get('break_reason', 'Incompatible change')}")
            
            if ext_file.get('affected_lines'):
                lines.append(f"**Affected Lines:** {', '.join(map(str, ext_file['affected_lines'][:5]))}")
            
            lines.append("")
    
    # Breaking changes summary (NEW)
    if breaking_changes:
        lines.extend([
            "## 🚨 Breaking Changes Detected",
            "",
        ])
        for change in breaking_changes:
            lines.append(f"- {change}")
        lines.append("")
        lines.extend([
            "**Review with this context:**",
            "- Will the changes break any of the external files?",
            "- Are there missing exception handlers that external callers expect?",
            "- Is the change backward compatible with external usage?",
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
