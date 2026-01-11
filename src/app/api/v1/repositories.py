# src/app/api/v1/repositories.py
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ....core.database import get_session
from ....core.repositories import ReviewRepository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


async def get_repo():
    async with get_session() as session:
        yield ReviewRepository(session)

Repo = Annotated[ReviewRepository, Depends(get_repo)]


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class ConfigUpdate(BaseModel):
    enabled: bool | None = None
    auto_review: bool | None = None
    review_on_update: bool | None = None
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    output_language: str | None = None
    slack_channel: str | None = None
    slack_notify_on: str | None = None
    github_comment: bool | None = None
    agents: dict[str, bool] | None = None


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.get("")
async def list_repositories(repo: Repo) -> list[dict]:
    repos = await repo.list_repos()
    return [r.to_dict() for r in repos]


@router.get("/{repo_id}")
async def get_repository(repo_id: int, repo: Repo) -> dict:
    repository = await repo.get_repo(repo_id)
    if not repository:
        raise HTTPException(404, "Repository not found")
    return repository.to_dict()


@router.get("/{repo_id}/config")
async def get_config(repo_id: int, repo: Repo) -> dict[str, Any]:
    repository = await repo.get_repo(repo_id)
    if not repository:
        raise HTTPException(404, "Repository not found")
    config = await repo.get_or_create_config(repo_id)
    return config.to_dict()


@router.put("/{repo_id}/config")
async def update_config(repo_id: int, data: ConfigUpdate, repo: Repo) -> dict[str, Any]:
    repository = await repo.get_repo(repo_id)
    if not repository:
        raise HTTPException(404, "Repository not found")
    config = await repo.update_config(repo_id, data.model_dump(exclude_none=True))
    
    # Invalidate cache
    from ....core.services import get_config_service
    config_service = await get_config_service()
    await config_service.invalidate(repository.owner, repository.name)
    
    return config.to_dict()
