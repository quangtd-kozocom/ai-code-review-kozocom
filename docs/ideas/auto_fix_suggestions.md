# 🔧 Auto-Fix Suggestions (One-Click Fix)

> Tự động tạo patch sửa lỗi và cho phép apply trực tiếp từ PR comment

**Độ ưu tiên:** 🔴 Cao  
**Độ phức tạp:** Trung bình  
**Tham khảo:** CodeRabbit One-Click Fix, Cursor Bugbot

---

## 📋 Mô Tả

Thay vì chỉ comment về vấn đề được phát hiện, hệ thống sẽ:

1. Phân tích lỗi cụ thể
2. Tạo patch/suggestion code để sửa
3. Hiển thị trong GitHub PR với format suggestion block
4. Developer có thể click "Commit suggestion" để apply ngay

---

## 🎯 Mục Tiêu

- **Primary:** Giảm thời gian fix issues từ phút xuống giây
- **Secondary:** Tăng tỷ lệ issues được sửa (thay vì bỏ qua)
- **Tertiary:** Học hỏi từ các fix patterns của developer

---

## 💡 Cách Hoạt Động

### Flow Diagram

```
┌─────────────────┐
│   Issue Found   │
│  by AI Agent    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analyze Code   │
│    Context      │
│ (surrounding    │
│   lines, file)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Generate      │
│  Fix Patch      │
│  using LLM      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validate Fix    │
│ (syntax check,  │
│  AST parsing)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Post GitHub    │
│  Suggestion     │
│    Comment      │
└─────────────────┘
```

### GitHub Suggestion Format

```markdown
🔴 **CRITICAL** (security) - SQL Injection vulnerability

**Issue:** String concatenation in SQL query allows injection attacks.

**Suggestion:**
\`\`\`suggestion
cursor.execute("SELECT \* FROM users WHERE id = ?", (user_id,))
\`\`\`

**Explanation:** Use parameterized queries to prevent SQL injection.
The `?` placeholder safely escapes user input.

[✅ Accept Fix] [💬 Discuss] [❌ Dismiss]
```

---

## 🛠️ Technical Implementation

### 1. Extend ReviewComment Model

```python
# src/agents/state.py

class ReviewComment(BaseModel):
    """A review comment from an agent."""
    file: str
    line: int
    end_line: int | None = None  # NEW: For multi-line suggestions
    severity: Literal["critical", "warning", "info", "suggestion"]
    category: str
    message: str
    suggestion: str | None = None

    # NEW: Auto-fix fields
    fix_available: bool = False
    fix_code: str | None = None  # The actual fix code
    fix_explanation: str | None = None
    fix_confidence: float = 0.0  # How confident the fix is correct

    confidence: float = Field(ge=0.0, le=1.0)
    agent: str
```

### 2. Fix Generation Prompt

````python
# src/agents/prompts/fix_generator.py

FIX_PROMPT = """You are an expert code fixer.

## Issue Detected:
- File: {filename}
- Line: {line}
- Issue: {issue_message}
- Category: {category}

## Original Code:
```{language}
{original_code}
````

## Surrounding Context:

```{language}
{context_before}
--- ISSUE LINE ---
{original_code}
--- END ISSUE ---
{context_after}
```

## Task:

Generate a MINIMAL fix that resolves the issue without changing other functionality.

## Rules:

1. Only modify the problematic lines
2. Keep the same code style and indentation
3. Ensure the fix is syntactically correct
4. Provide a brief explanation

## Output (JSON only):

{{
  "fixed_code": "the corrected code lines",
  "explanation": "why this fix works",
  "confidence": 0.95
}}
"""

````

### 3. New Fix Generator Node

```python
# src/agents/nodes/fix_generator.py

async def run(state: GraphState) -> dict:
    """Generate fix suggestions for detected issues."""
    llm = get_llm()
    comments_with_fixes = []

    for comment in state["comments"]:
        if comment.severity in ["critical", "warning"]:
            # Get surrounding context
            context = await _get_code_context(
                state["files"],
                comment.file,
                comment.line
            )

            prompt = FIX_PROMPT.format(
                filename=comment.file,
                line=comment.line,
                issue_message=comment.message,
                category=comment.category,
                language=_get_language(comment.file),
                original_code=context["target"],
                context_before=context["before"],
                context_after=context["after"],
            )

            response = await llm.ainvoke(prompt)
            fix_data = _parse_fix_response(response.content)

            if fix_data and fix_data["confidence"] > 0.8:
                comment = comment.model_copy(update={
                    "fix_available": True,
                    "fix_code": fix_data["fixed_code"],
                    "fix_explanation": fix_data["explanation"],
                    "fix_confidence": fix_data["confidence"],
                })

        comments_with_fixes.append(comment)

    return {"comments": comments_with_fixes}


async def _get_code_context(
    files: list[FileChange],
    filename: str,
    line: int,
    context_lines: int = 5
) -> dict:
    """Extract code context around the issue line."""
    for f in files:
        if f.filename == filename:
            patch_lines = f.patch.split('\n')
            # Parse diff to find actual line content
            # ... implementation details
            return {
                "before": ...,
                "target": ...,
                "after": ...,
            }
    return {"before": "", "target": "", "after": ""}
````

### 4. Update GitHub Publisher

````python
# src/agents/nodes/github_publisher.py

def _format_comment_with_fix(c: ReviewComment) -> str:
    """Format comment with GitHub suggestion block if fix available."""
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "💡"}

    body = f"{emoji.get(c.severity, '•')} **{c.severity.upper()}** ({c.category})\n\n"
    body += f"{c.message}\n\n"

    if c.fix_available and c.fix_code:
        # GitHub's special suggestion syntax
        body += "**Suggested Fix:**\n"
        body += f"```suggestion\n{c.fix_code}\n```\n\n"
        body += f"*{c.fix_explanation}* (Confidence: {c.fix_confidence:.0%})\n"
    elif c.suggestion:
        body += f"**Manual Fix:** {c.suggestion}\n"

    return body
````

### 5. Update Graph Flow

```python
# src/agents/graph.py

def create_graph() -> StateGraph:
    g = StateGraph(GraphState)

    # Existing nodes
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)

    # NEW: Fix generation node
    g.add_node("generate_fixes", fix_generator.run)

    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # Flow
    g.set_entry_point("extract")
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")

    # NEW: Generate fixes after aggregation
    g.add_edge("aggregate", "generate_fixes")
    g.add_edge("generate_fixes", "publish")

    g.add_edge("publish", "notify")
    g.add_edge("notify", END)

    return g.compile()
```

---

## ✅ Acceptance Criteria

1. [ ] Critical và Warning issues có "Suggested Fix" block
2. [ ] Fix code được format đúng GitHub suggestion syntax
3. [ ] Developer có thể click "Commit suggestion" trực tiếp
4. [ ] Confidence score hiển thị để developer biết độ tin cậy
5. [ ] Fallback về suggestion text nếu không generate được fix

---

## 📊 Metrics

| Metric                    | Target |
| ------------------------- | ------ |
| Issues với fix available  | > 70%  |
| Fix confidence trung bình | > 85%  |
| Fix acceptance rate       | > 40%  |
| False positive rate       | < 10%  |

---

## ⚠️ Edge Cases & Risks

1. **Fix không compile:** Cần validation bước sau
2. **Fix sai logic:** Cần human review, hiển thị confidence
3. **Multi-line changes:** Xử lý `end_line` cho suggestion blocks
4. **Rate limiting:** Thêm calls tới LLM cho mỗi issue

---

## 🔮 Future Enhancements

1. **Batch Fix:** Apply tất cả fixes cùng lúc
2. **Fix Preview:** Show diff preview trước khi apply
3. **Learn from Rejections:** Cải thiện từ các fix bị reject
4. **AST Validation:** Validate fix code qua AST parser
