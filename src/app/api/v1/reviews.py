# src/app/api/v1/reviews.py
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ....core.database import get_session
from ....core.repositories import ReviewRepository

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# ─────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────
async def get_repo():
    async with get_session() as session:
        yield ReviewRepository(session)

Repo = Annotated[ReviewRepository, Depends(get_repo)]


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class AffectedCallerIn(BaseModel):
    file_path: str
    line_number: int | None = None
    call_text: str | None = None
    break_reason: str | None = None

class BreakingChangeIn(BaseModel):
    file_path: str
    line_number: int | None = None
    entity_type: str | None = None
    entity_name: str | None = None
    class_name: str | None = None
    change_type: str | None = None
    change_detail: str | None = None
    old_definition: str | None = None
    new_definition: str | None = None
    severity: str = "warning"
    recommendation: str | None = None
    affected_callers: list[AffectedCallerIn] = Field(default_factory=list)

class CommentIn(BaseModel):
    file_path: str
    line_number: int | None = None
    severity: str | None = None
    message: str | None = None
    recommendation: str | None = None
    affected_files: list[dict] | None = None
    github_comment_id: int | None = None

class ReviewIngest(BaseModel):
    owner: str
    repo: str
    pr_number: int
    installation_id: int
    pr_title: str | None = None
    pr_author: str | None = None
    base_branch: str | None = None
    head_branch: str | None = None
    status: str = "completed"
    skip_reason: str | None = None
    total_files: int = 0
    breaking_changes: list[BreakingChangeIn] = Field(default_factory=list)
    comments: list[CommentIn] = Field(default_factory=list)

class ReviewStats(BaseModel):
    totalReviews: int
    totalErrors: int
    avgErrorsPerReview: float
    securityIssues: int
    developerStats: list[dict] = Field(default_factory=list)
    errorTypes: dict = Field(default_factory=lambda: {"syntax": 0, "logic": 0, "security": 0})
    weeklyTrend: list[dict] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/ingest")
async def ingest_review(data: ReviewIngest, repo: Repo) -> dict[str, Any]:
    repository = await repo.get_or_create_repo(data.owner, data.repo, data.installation_id)
    if await repo.get_review_by_pr(repository.id, data.pr_number):
        raise HTTPException(400, f"Review for PR #{data.pr_number} already exists")

    critical = sum(1 for bc in data.breaking_changes if bc.severity == "critical")
    review = await repo.create_review({
        "repository_id": repository.id,
        "pr_number": data.pr_number,
        "pr_title": data.pr_title,
        "pr_author": data.pr_author,
        "base_branch": data.base_branch,
        "head_branch": data.head_branch,
        "status": data.status,
        "skip_reason": data.skip_reason,
        "total_files": data.total_files,
        "total_changes": len(data.breaking_changes),
        "total_comments": len(data.comments),
        "count_critical": critical,
        "count_warning": len(data.breaking_changes) - critical,
        "completed_at": datetime.now() if data.status == "completed" else None,
    })

    for bc in data.breaking_changes:
        await repo.add_breaking_change(review.id, bc.model_dump(exclude={"affected_callers"}), [c.model_dump() for c in bc.affected_callers])
    for c in data.comments:
        await repo.add_comment(review.id, c.model_dump())

    repository.last_review_at = datetime.now()
    return {"success": True, "review_id": review.id}


@router.get("")
async def list_reviews(repo: Repo, period: str | None = None, repository_id: int | None = None, skip: int = 0, limit: int = 20) -> list[dict]:
    reviews = await repo.list_reviews(skip, limit, period, repository_id)
    return [r.to_dict() for r in reviews]


@router.get("/stats")
async def get_stats(repo: Repo, period: str | None = None) -> ReviewStats:
    stats = await repo.get_stats(period)
    return ReviewStats(
        totalReviews=stats["totalReviews"],
        totalErrors=stats["totalErrors"],
        avgErrorsPerReview=stats["avgErrorsPerReview"],
        securityIssues=stats["securityIssues"],
        developerStats=await repo.get_developer_stats(period),
        errorTypes={"syntax": 0, "logic": stats["totalErrors"], "security": stats["securityIssues"]},
        weeklyTrend=await repo.get_weekly_trend(),
    )


@router.get("/{review_id}")
async def get_review(review_id: int, repo: Repo) -> dict[str, Any]:
    review = await repo.get_review(review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    result = review.to_dict()
    bcs = await repo.get_breaking_changes(review_id)
    breaking_changes = []
    for bc in bcs:
        bc_dict = bc.to_dict()
        bc_dict["affected_callers"] = [c.to_dict() for c in await repo.get_affected_callers(bc.id)]
        breaking_changes.append(bc_dict)
    result["breaking_changes"] = breaking_changes
    result["comments"] = [c.to_dict() for c in await repo.get_comments(review_id)]
    return result
