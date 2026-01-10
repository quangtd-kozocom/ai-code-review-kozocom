"""Function review prompts for targeted LLM review.

Provides structured prompts for reviewing individual functions
with precise context and targeted questions.
"""

SYSTEM_PROMPT = """You are an expert code reviewer focusing exclusively on breaking changes and caller impact.

## 🎯 PRIMARY FOCUS: BREAKING CHANGES & IMPACT

Your ONLY job is to identify changes that will break existing code or cause runtime failures:

1. **Signature Changes** - Will existing callers break?
   - Added required parameters without defaults
   - Removed parameters that callers depend on
   - Changed parameter types incompatibly
   - Changed return type that breaks caller expectations

2. **Caller Impact** - Will code that uses this function fail?
   - Existing callers shown in context will break
   - Exception types changed or added (callers may not catch)
   - Return value contract changed (null when not expected, different type)

3. **Business Logic Errors** - Incorrect behavior
   - Wrong calculations or algorithms
   - Missing required validation for business rules
   - Data integrity issues (e.g., saving invalid state)

4. **Missing Required Parameters** - Parameters that should be required but aren't validated
   - Function expects non-null but doesn't check
   - Required business data not validated

## 🚫 DO NOT REPORT

- Test coverage issues
- Code style or formatting
- Performance optimizations
- General "best practices"
- Refactoring suggestions
- Documentation quality

## 🛡️ ANTI-HALLUCINATION PROTOCOL

Before reporting ANY issue:
1. **CITE EXACT CODE**: Quote the specific line that proves the issue
2. **VERIFY CALLERS**: If callers are shown, identify which ones will break and WHY
3. **CHECK DEPENDENCIES**: If callee source provided, verify its behavior
4. **BE SPECIFIC**: Don't say "might break" - say "WILL break CheckoutController.php:45 because..."

## 📊 CONFIDENCE CALIBRATION

- **0.95**: Definite breaking change with proof (signature changed + callers shown)
- **0.85**: High-likelihood breaking change (signature changed, callers likely affected)
- **0.75**: Potential breaking change with context evidence
- **< 0.7**: Don't report - will be filtered out

## Output Format
Respond with a JSON object containing a "findings" array.
Each finding must have:
- line: int (the line number in the new code)
- severity: "critical" | "warning" (only these two - no info/suggestion)
- message: str (clear explanation focusing on WHAT will break)
- suggestion: str | null (how to fix it)
- confidence: float (0.0 to 1.0, use calibration above)
- affected_files: list[str] (files/callers that will break - extract from context)
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
    
    # Callers context - CRITICAL for breaking change detection
    if callers:
        lines.extend([
            f"## ⚠️ Callers ({len(callers)} functions call this - WILL THEY BREAK?)",
            "",
            "**For each caller below, determine if it will break and WHY:**",
            "",
        ])
        for caller in callers[:5]:
            lines.extend([
                f"### `{caller['name']}` in `{caller['file']}:{caller.get('line', '?')}`",
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
    
    # External files context - Files outside PR that depend on this code
    if external_files:
        lines.extend([
            f"## 📁 External Files Affected ({len(external_files)} files outside PR)",
            "",
            "**These files are NOT in the PR but depend on this code:**",
            "**Determine if each will break and explain WHY:**",
            "",
        ])
        
        for ext_file in external_files[:10]:  # Limit to 10
            lines.append(f"### `{ext_file.get('path', 'Unknown')}`")
            
            if ext_file.get('usage_type'):
                lines.append(f"**Usage:** {ext_file.get('usage_type')}")
            
            if ext_file.get('references'):
                lines.append(f"**References:** {', '.join(ext_file['references'])}")
            
            if ext_file.get('affected_lines'):
                lines.append(f"**Lines:** {', '.join(map(str, ext_file['affected_lines'][:5]))}")
            
            # Show snippet if available
            if ext_file.get('content'):
                content_preview = ext_file['content'][:500]
                lines.extend([
                    "**Code snippet:**",
                    "```python",
                    content_preview,
                    "```",
                ])
            
            lines.append("")
    
    # Breaking changes summary
    if breaking_changes:
        lines.extend([
            "## 🚨 Breaking Changes Detected",
            "",
        ])
        for change in breaking_changes:
            lines.append(f"- {change}")
        lines.append("")
        lines.extend([
            "**CRITICAL: For each caller/external file, specify:**",
            "1. Which file/line will break",
            "2. WHY it will break (be specific)",
            "3. What needs to change to fix it",
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
                "## Review Instructions (DEEP - Breaking Changes Focus)",
                "",
                "Analyze for breaking changes:",
                "- Will signature changes break callers? (List specific files/lines)",
                "- Will exception changes break error handlers?",
                "- Will return type changes break caller expectations?",
                "- Are there business logic errors?",
                "- For EACH affected file, explain WHY it breaks",
                "",
            ])
        case "standard":
            lines.extend([
                "## Review Instructions (STANDARD - Breaking Changes Focus)",
                "",
                "Check for:",
                "- Breaking signature changes affecting callers",
                "- Business logic errors",
                "- Missing required parameter validation",
                "- List specific files that will break and WHY",
                "",
            ])
        case "quick":
            lines.extend([
                "## Review Instructions (QUICK - Breaking Changes Focus)",
                "",
                "Quick check for:",
                "- Critical breaking changes",
                "- Which callers will fail",
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
