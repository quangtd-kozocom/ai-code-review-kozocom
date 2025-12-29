# 🔄 Re-review Command

> Trigger lại review sau khi developer sửa code

**Độ ưu tiên:** 🔴 Cao  
**Độ phức tạp:** Thấp  
**Tham khảo:** [CodeRabbit Review Command](https://docs.coderabbit.ai/guides/commands)

---

## 📋 Mô Tả

Cho phép developer yêu cầu AI review lại PR sau khi đã sửa code theo suggestions trước đó.

### Use Cases

1. Developer đã fix issues → muốn verify
2. Thêm commits mới → cần review incremental
3. Force full review → bỏ qua cache/history

---

## 🎯 Mục Tiêu

- **Primary:** Continuous feedback loop
- **Secondary:** Verify fixes before merge
- **Tertiary:** Reduce back-and-forth với human reviewers

---

## 💡 Command Usage

```markdown
# Incremental review (only new changes)

@reviewer re-review

# Full review (ignore previous comments)

@reviewer full review

# Review specific files only

@reviewer review src/auth.py src/utils.py
```

### Example Interaction

```markdown
Developer: @reviewer re-review

Bot: 🔄 **Re-reviewing PR #42**

Analyzing changes since last review...

## ✅ Fixed Issues (3)

- ~~SQL Injection in `auth.py:15`~~ - Fixed with parameterized query
- ~~Missing null check in `utils.py:28`~~ - Added validation
- ~~Hardcoded secret in `config.py:5`~~ - Moved to env var

## 🆕 New Issues Found (1)

- **Warning** (style) `auth.py:22`: Consider using `pathlib` instead of string concatenation

## 📊 Summary

| Metric   | Before | After |
| -------- | ------ | ----- |
| Critical | 2      | 0 ✅  |
| Warning  | 3      | 1     |
| Info     | 5      | 3     |

_Great progress! One minor style issue remaining._
```

---

## 🛠️ Technical Implementation

### 1. Add Command Types

```python
# src/chat/commands.py

class CommandType(StrEnum):
    FIX = "fix"
    GENERATE_TESTS = "generate_tests"
    EXPLAIN = "explain"
    HELP = "help"
    RE_REVIEW = "re_review"      # NEW
    FULL_REVIEW = "full_review"  # NEW
    UNKNOWN = "unknown"
```

### 2. Add Parser Patterns

```python
# src/chat/parser.py

_PATTERNS: dict[CommandType, re.Pattern[str]] = {
    # ... existing ...
    CommandType.RE_REVIEW: re.compile(
        r"@reviewer\s+re-?review", re.IGNORECASE
    ),
    CommandType.FULL_REVIEW: re.compile(
        r"@reviewer\s+full\s+review", re.IGNORECASE
    ),
}
```

### 3. Create Handler

```python
# src/chat/handler.py

class ReReviewCommandHandler(BaseCommandHandler):
    """Trigger incremental or full re-review."""

    async def execute(self, ctx: CommandContext) -> str:
        try:
            # Get previous review comments by bot
            previous_comments = await self.github.get_bot_review_comments(
                ctx.owner, ctx.repo, ctx.pr_number
            )

            # Get current PR state
            pr_files = await self.github.get_pr_files(
                ctx.owner, ctx.repo, ctx.pr_number
            )

            # Determine review type
            is_full = ctx.command_type == CommandType.FULL_REVIEW

            if is_full:
                # Full review - ignore history
                await self._trigger_full_review(ctx)
                return "🔄 Full review triggered. Results will be posted shortly."
            else:
                # Incremental - check what's fixed
                fixed, remaining = await self._analyze_fixes(
                    previous_comments, pr_files
                )

                # Trigger review for new changes only
                await self._trigger_incremental_review(ctx, previous_comments)

                return self._format_re_review_response(fixed, remaining)

        except Exception as e:
            log.exception("Re-review failed")
            return f"❌ Error: {e}"

    async def _analyze_fixes(
        self,
        previous: list[dict],
        current_files: list[dict]
    ) -> tuple[list, list]:
        """Analyze which previous issues have been fixed."""
        fixed = []
        remaining = []

        for comment in previous:
            file_path = comment.get("path")
            line = comment.get("line")

            # Check if the problematic code still exists
            current_content = self._get_file_content(current_files, file_path)

            if self._issue_still_exists(comment, current_content):
                remaining.append(comment)
            else:
                fixed.append(comment)

        return fixed, remaining

    async def _trigger_full_review(self, ctx: CommandContext):
        """Trigger full review via Celery task."""
        from ..workers.tasks import process_pr_review

        process_pr_review.delay(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            installation_id=ctx.installation_id,
            force_full=True,
        )

    async def _trigger_incremental_review(
        self,
        ctx: CommandContext,
        exclude_comments: list[dict]
    ):
        """Trigger incremental review, excluding already-reviewed lines."""
        from ..workers.tasks import process_pr_review

        # Extract lines to exclude
        exclude_lines = {
            (c["path"], c["line"]) for c in exclude_comments
        }

        process_pr_review.delay(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            installation_id=ctx.installation_id,
            exclude_lines=list(exclude_lines),
        )
```

### 4. GitHub Service Extension

```python
# src/app/services/github.py

async def get_bot_review_comments(
    self,
    owner: str,
    repo: str,
    pr_number: int
) -> list[dict]:
    """Get all review comments made by this bot."""
    comments = await self.get_pr_review_comments(owner, repo, pr_number)

    # Filter to bot's comments only
    bot_login = "ai-reviewer[bot]"  # or from config
    return [c for c in comments if c.get("user", {}).get("login") == bot_login]
```

---

## ✅ Acceptance Criteria

1. [ ] `@reviewer re-review` triggers incremental review
2. [ ] `@reviewer full review` triggers complete review
3. [ ] Response shows fixed vs remaining issues
4. [ ] New issues in updated code are detected
5. [ ] Performance: incremental faster than full

---

## 📊 Metrics

| Metric                   | Target       |
| ------------------------ | ------------ |
| Re-review response time  | < 30 seconds |
| Fix detection accuracy   | > 95%        |
| False positive (unfixed) | < 5%         |

---

## 🔮 Future Enhancements

1. **Auto re-review:** Trigger after each push
2. **Diff view:** Show before/after comparison
3. **Progress tracking:** Track issues over multiple iterations
4. **Approval suggestion:** Suggest approval when all critical fixed
