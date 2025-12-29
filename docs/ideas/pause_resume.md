# ⏸️ Pause/Resume Reviews

> Tạm dừng và tiếp tục auto-review cho PR cụ thể

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Thấp  
**Tham khảo:** [CodeRabbit Pause Command](https://docs.coderabbit.ai/guides/commands)

---

## 📋 Mô Tả

Cho phép developer tạm dừng auto-review khi:

1. PR đang WIP (Work In Progress)
2. Chỉ cần review cuối cùng trước merge
3. Đang experiment/draft

---

## 🎯 Mục Tiêu

- **Primary:** Reduce noise từ WIP reviews
- **Secondary:** Save API costs
- **Tertiary:** Developer control over review timing

---

## 💡 Command Usage

```markdown
# Pause auto-reviews

@reviewer pause

# Resume auto-reviews

@reviewer resume

# Ignore this PR entirely (until re-enabled)

@reviewer ignore
```

### Example Interaction

```markdown
Developer: @reviewer pause

Bot: ⏸️ **Auto-reviews paused for PR #42**

I won't automatically review new commits until you run `@reviewer resume`.

You can still use on-demand commands:

- `@reviewer fix` - Generate fixes
- `@reviewer explain` - Get explanations
- `@reviewer summarize` - Summarize changes

---

Developer: @reviewer resume

Bot: ▶️ **Auto-reviews resumed for PR #42**

I'll now review new commits automatically.
Running review on latest changes...
```

---

## 🛠️ Technical Implementation

### 1. Add Command Types

```python
# src/chat/commands.py

class CommandType(StrEnum):
    # ... existing ...
    PAUSE = "pause"
    RESUME = "resume"
    IGNORE = "ignore"
```

### 2. State Storage

```python
# src/core/pr_state.py

from enum import StrEnum
from datetime import datetime
from redis import Redis

class PRReviewState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    IGNORED = "ignored"

class PRStateManager:
    """Manage review state for PRs."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = "pr_state:"

    def _key(self, owner: str, repo: str, pr_number: int) -> str:
        return f"{self.prefix}{owner}/{repo}/{pr_number}"

    async def set_state(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        state: PRReviewState,
        by_user: str,
    ) -> None:
        """Set PR review state."""
        key = self._key(owner, repo, pr_number)
        data = {
            "state": state.value,
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": by_user,
        }
        await self.redis.hset(key, mapping=data)
        # Auto-expire after 30 days of inactivity
        await self.redis.expire(key, 30 * 24 * 60 * 60)

    async def get_state(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> PRReviewState:
        """Get PR review state."""
        key = self._key(owner, repo, pr_number)
        data = await self.redis.hgetall(key)

        if not data:
            return PRReviewState.ACTIVE

        return PRReviewState(data.get("state", "active"))

    async def should_auto_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> bool:
        """Check if PR should be auto-reviewed."""
        state = await self.get_state(owner, repo, pr_number)
        return state == PRReviewState.ACTIVE
```

### 3. Webhook Integration

```python
# src/app/api/v1/webhooks.py

async def github_webhook(...):
    # ... existing validation ...

    if x_github_event == "pull_request":
        if action in ["opened", "synchronize"]:
            pr_number = payload["pull_request"]["number"]

            # Check if reviews are paused
            state_manager = PRStateManager(get_redis())
            if not await state_manager.should_auto_review(owner, repo, pr_number):
                log.info("Skipping review - paused", pr=pr_number)
                return {"status": "skipped", "reason": "paused"}

            # Continue with review...
```

### 4. Command Handlers

```python
# src/chat/handler.py

class PauseCommandHandler(BaseCommandHandler):
    """Pause auto-reviews for this PR."""

    async def execute(self, ctx: CommandContext) -> str:
        state_manager = PRStateManager(get_redis())

        await state_manager.set_state(
            ctx.owner,
            ctx.repo,
            ctx.pr_number,
            PRReviewState.PAUSED,
            ctx.author,
        )

        return """⏸️ **Auto-reviews paused for this PR**

I won't automatically review new commits until you run `@reviewer resume`.

You can still use on-demand commands:
- `@reviewer fix` - Generate fixes
- `@reviewer explain` - Get explanations
- `@reviewer summarize` - Summarize changes
"""


class ResumeCommandHandler(BaseCommandHandler):
    """Resume auto-reviews for this PR."""

    async def execute(self, ctx: CommandContext) -> str:
        state_manager = PRStateManager(get_redis())

        await state_manager.set_state(
            ctx.owner,
            ctx.repo,
            ctx.pr_number,
            PRReviewState.ACTIVE,
            ctx.author,
        )

        # Optionally trigger immediate review
        from ..workers.tasks import process_pr_review
        process_pr_review.delay(
            owner=ctx.owner,
            repo=ctx.repo,
            pr_number=ctx.pr_number,
            installation_id=ctx.installation_id,
        )

        return """▶️ **Auto-reviews resumed for this PR**

I'll now review new commits automatically.
Running review on latest changes...
"""


class IgnoreCommandHandler(BaseCommandHandler):
    """Ignore this PR entirely."""

    async def execute(self, ctx: CommandContext) -> str:
        state_manager = PRStateManager(get_redis())

        await state_manager.set_state(
            ctx.owner,
            ctx.repo,
            ctx.pr_number,
            PRReviewState.IGNORED,
            ctx.author,
        )

        return """🚫 **This PR is now ignored**

I won't review this PR until you run `@reviewer resume`.
"""
```

---

## ✅ Acceptance Criteria

1. [ ] `@reviewer pause` stops auto-reviews
2. [ ] `@reviewer resume` re-enables auto-reviews
3. [ ] `@reviewer ignore` permanently disables until resume
4. [ ] On-demand commands still work when paused
5. [ ] State persists across webhook events

---

## 📊 Metrics

| Metric           | Target            |
| ---------------- | ----------------- |
| Paused PRs       | Track count       |
| Resume rate      | > 80%             |
| API cost savings | Measure reduction |

---

## 🔮 Future Enhancements

1. **Auto-pause drafts:** Pause for draft PRs
2. **Schedule:** Pause until specific time
3. **Pause reasons:** Track why paused
4. **Team settings:** Default pause behavior
