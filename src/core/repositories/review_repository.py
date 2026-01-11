# src/core/repositories/review_repository.py
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Repository, PRReview, BreakingChange, AffectedCaller, ReviewComment

COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444", "#84cc16", "#06b6d4", "#f97316"]


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ─────────────────────────────────────────────────────────────
    # Repository
    # ─────────────────────────────────────────────────────────────
    async def get_or_create_repo(self, owner: str, name: str, installation_id: int) -> Repository:
        result = await self.session.execute(select(Repository).where(Repository.owner == owner, Repository.name == name))
        if repo := result.scalars().first():
            return repo
        repo = Repository(owner=owner, name=name, installation_id=installation_id)
        self.session.add(repo)
        await self.session.flush()
        return repo

    async def list_repos(self) -> list[Repository]:
        result = await self.session.execute(select(Repository).order_by(Repository.last_review_at.desc()))
        return list(result.scalars().all())

    async def get_repo(self, repo_id: int) -> Repository | None:
        return await self.session.get(Repository, repo_id)

    # ─────────────────────────────────────────────────────────────
    # PR Review
    # ─────────────────────────────────────────────────────────────
    async def create_review(self, data: dict[str, Any]) -> PRReview:
        review = PRReview(**data)
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def get_review(self, review_id: int) -> PRReview | None:
        result = await self.session.execute(select(PRReview).where(PRReview.id == review_id))
        return result.scalars().first()

    async def get_review_by_pr(self, repository_id: int, pr_number: int) -> PRReview | None:
        result = await self.session.execute(
            select(PRReview).where(PRReview.repository_id == repository_id, PRReview.pr_number == pr_number)
        )
        return result.scalars().first()

    async def list_reviews(self, skip: int = 0, limit: int = 20, period: str | None = None, repository_id: int | None = None) -> list[PRReview]:
        query = select(PRReview).order_by(PRReview.created_at.desc())
        if period:
            days = {"week": 7, "month": 30, "quarter": 90}.get(period, 30)
            query = query.where(PRReview.created_at >= datetime.now() - timedelta(days=days))
        if repository_id:
            query = query.where(PRReview.repository_id == repository_id)
        result = await self.session.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────
    # Breaking Changes & Comments
    # ─────────────────────────────────────────────────────────────
    async def add_breaking_change(self, review_id: int, data: dict[str, Any], callers: list[dict] | None = None) -> BreakingChange:
        bc = BreakingChange(review_id=review_id, **data)
        self.session.add(bc)
        await self.session.flush()
        if callers:
            for c in callers:
                self.session.add(AffectedCaller(breaking_change_id=bc.id, **c))
            bc.affected_count = len(callers)
            await self.session.flush()
        return bc

    async def get_breaking_changes(self, review_id: int) -> list[BreakingChange]:
        result = await self.session.execute(select(BreakingChange).where(BreakingChange.review_id == review_id))
        return list(result.scalars().all())

    async def get_affected_callers(self, bc_id: int) -> list[AffectedCaller]:
        result = await self.session.execute(select(AffectedCaller).where(AffectedCaller.breaking_change_id == bc_id))
        return list(result.scalars().all())

    async def add_comment(self, review_id: int, data: dict[str, Any]) -> ReviewComment:
        comment = ReviewComment(review_id=review_id, **data)
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def get_comments(self, review_id: int) -> list[ReviewComment]:
        result = await self.session.execute(select(ReviewComment).where(ReviewComment.review_id == review_id))
        return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────────────────────
    async def get_stats(self, period: str | None = None) -> dict[str, Any]:
        days = {"week": 7, "month": 30, "quarter": 90}.get(period or "month", 30)
        since = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(
                func.count(PRReview.id).label("total"),
                func.coalesce(func.sum(PRReview.count_critical + PRReview.count_warning), 0).label("errors"),
                func.coalesce(func.sum(PRReview.count_critical), 0).label("critical"),
            ).where(PRReview.status == "completed", PRReview.created_at >= since)
        )
        row = result.first()
        total, errors, critical = (row[0] or 0, row[1] or 0, row[2] or 0) if row else (0, 0, 0)
        return {
            "totalReviews": total,
            "totalErrors": errors,
            "avgErrorsPerReview": round(errors / total, 1) if total else 0,
            "securityIssues": critical,
        }

    async def get_developer_stats(self, period: str | None = None, limit: int = 10) -> list[dict]:
        days = {"week": 7, "month": 30, "quarter": 90}.get(period or "month", 30)
        since = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(PRReview.pr_author, func.sum(PRReview.count_critical + PRReview.count_warning).label("errors"))
            .where(PRReview.status == "completed", PRReview.created_at >= since, PRReview.pr_author.isnot(None))
            .group_by(PRReview.pr_author)
            .order_by(func.sum(PRReview.count_critical + PRReview.count_warning).desc())
            .limit(limit)
        )
        return [{"name": r[0], "errors": r[1] or 0, "color": COLORS[i % len(COLORS)]} for i, r in enumerate(result.all())]

    async def get_weekly_trend(self, weeks: int = 8) -> list[dict]:
        since = datetime.now() - timedelta(weeks=weeks)
        week_col = func.date_trunc("week", PRReview.created_at).label("week")
        result = await self.session.execute(
            select(week_col, func.sum(PRReview.count_critical + PRReview.count_warning).label("errors"))
            .where(PRReview.status == "completed", PRReview.created_at >= since)
            .group_by(week_col)
            .order_by(week_col)
        )
        return [{"week": r[0].strftime("%b %d") if r[0] else "", "errors": r[1] or 0} for r in result.all()]
