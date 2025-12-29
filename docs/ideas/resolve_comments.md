# ✅ Resolve Comments

> Auto-resolve tất cả AI review comments

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Thấp  
**Tham khảo:** [CodeRabbit Resolve Command](https://docs.coderabbit.ai/guides/commands)

---

## 📋 Mô Tả

Cho phép developer nhanh chóng resolve tất cả review comments từ AI bot khi:

1. Đã fix xong tất cả issues
2. Muốn clean up PR conversation
3. Disagree với suggestions và muốn dismiss

---

## 🎯 Mục Tiêu

- **Primary:** Clean PR conversation
- **Secondary:** Signal "done" to human reviewers
- **Tertiary:** Track resolution patterns

---

## 💡 Command Usage

```markdown
# Resolve all bot comments

@reviewer resolve

# Resolve with reason

@reviewer resolve --reason "Fixed in latest commit"

# Resolve specific comment thread

@reviewer resolve this
```

### Example Interaction

```markdown
Developer: @reviewer resolve

Bot: ✅ **Resolved 5 review comments**

| Status          | Count |
| --------------- | ----- |
| 🔧 Fixed        | 3     |
| 👎 Dismissed    | 1     |
| ℹ️ Acknowledged | 1     |

All AI review threads have been resolved.
Human reviewer comments are still pending.
```

---

## 🛠️ Technical Implementation

### 1. Add Command Type

```python
# src/chat/commands.py

class CommandType(StrEnum):
    # ... existing ...
    RESOLVE = "resolve"
```

### 2. GitHub API Extension

```python
# src/app/services/github.py

async def resolve_review_thread(
    self,
    owner: str,
    repo: str,
    thread_id: int,
) -> bool:
    """Resolve a review thread using GraphQL."""
    # GitHub REST API doesn't support resolving threads
    # Need to use GraphQL

    query = """
    mutation ResolveThread($threadId: ID!) {
        resolveReviewThread(input: {threadId: $threadId}) {
            thread {
                isResolved
            }
        }
    }
    """

    try:
        result = await self._graphql(query, {"threadId": thread_id})
        return result["resolveReviewThread"]["thread"]["isResolved"]
    except Exception as e:
        log.error("Failed to resolve thread", thread_id=thread_id, error=str(e))
        return False

async def get_bot_review_threads(
    self,
    owner: str,
    repo: str,
    pr_number: int,
) -> list[dict]:
    """Get all unresolved review threads by bot."""
    query = """
    query GetReviewThreads($owner: String!, $repo: String!, $pr: Int!) {
        repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
                reviewThreads(first: 100) {
                    nodes {
                        id
                        isResolved
                        comments(first: 1) {
                            nodes {
                                author {
                                    login
                                }
                                body
                            }
                        }
                    }
                }
            }
        }
    }
    """

    result = await self._graphql(query, {
        "owner": owner,
        "repo": repo,
        "pr": pr_number,
    })

    threads = result["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    bot_login = "ai-reviewer[bot]"

    # Filter to bot's unresolved threads
    return [
        t for t in threads
        if not t["isResolved"]
        and t["comments"]["nodes"]
        and t["comments"]["nodes"][0]["author"]["login"] == bot_login
    ]
```

### 3. Command Handler

```python
# src/chat/handler.py

class ResolveCommandHandler(BaseCommandHandler):
    """Resolve all bot review comments."""

    async def execute(self, ctx: CommandContext) -> str:
        try:
            # Get all unresolved bot threads
            threads = await self.github.get_bot_review_threads(
                ctx.owner, ctx.repo, ctx.pr_number
            )

            if not threads:
                return "ℹ️ No unresolved AI review comments found."

            # Resolve each thread
            resolved_count = 0
            failed_count = 0

            for thread in threads:
                success = await self.github.resolve_review_thread(
                    ctx.owner, ctx.repo, thread["id"]
                )
                if success:
                    resolved_count += 1
                else:
                    failed_count += 1

            # Track for learning
            await self._record_resolution(ctx, threads, ctx.options.get("reason"))

            return self._format_response(resolved_count, failed_count, len(threads))

        except Exception as e:
            log.exception("Resolve failed")
            return f"❌ Error resolving comments: {e}"

    async def _record_resolution(
        self,
        ctx: CommandContext,
        threads: list[dict],
        reason: str | None,
    ):
        """Record resolution for learning system."""
        # Future: feed into learning system
        log.info(
            "Comments resolved",
            pr=ctx.pr_number,
            count=len(threads),
            reason=reason,
            author=ctx.author,
        )

    def _format_response(
        self,
        resolved: int,
        failed: int,
        total: int,
    ) -> str:
        if failed == 0:
            return f"""✅ **Resolved {resolved} review comments**

All AI review threads have been marked as resolved.
Human reviewer comments are still pending.
"""
        else:
            return f"""⚠️ **Partially resolved**

| Status | Count |
|--------|-------|
| ✅ Resolved | {resolved} |
| ❌ Failed | {failed} |

Some threads could not be resolved. Please resolve manually.
"""
```

---

## ✅ Acceptance Criteria

1. [ ] `@reviewer resolve` resolves all bot threads
2. [ ] Uses GitHub GraphQL API for resolution
3. [ ] Only resolves bot's own comments
4. [ ] Reports success/failure count
5. [ ] Preserves human reviewer comments

---

## 📊 Metrics

| Metric                       | Target        |
| ---------------------------- | ------------- |
| Threads resolved per command | Track average |
| Resolution success rate      | > 99%         |
| Time saved per PR            | ~2 minutes    |

---

## 🔮 Future Enhancements

1. **Selective resolve:** Resolve by severity
2. **Bulk resolve:** Resolve across multiple PRs
3. **Learning integration:** Track patterns
4. **Reaction-based:** 👍 to resolve single thread
