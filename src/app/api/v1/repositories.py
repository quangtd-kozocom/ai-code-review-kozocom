# src/app/api/v1/repositories.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException

from ....core.database import get_session
from ....core.repositories import ReviewRepository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


async def get_repo():
    async with get_session() as session:
        yield ReviewRepository(session)

Repo = Annotated[ReviewRepository, Depends(get_repo)]


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
