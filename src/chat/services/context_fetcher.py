"""Context fetcher for fix command."""

import asyncio
import re
from dataclasses import dataclass, field

import structlog

from ...app.services.github import GitHubService

log = structlog.get_logger()

ENTITY_PATTERN = re.compile(r"(?:constant|method|function|class)\s+[`'\"]?(\w+)[`'\"]?", re.I)
FILE_PATTERN = re.compile(r"(\S+\.(?:php|py|js|ts|java|go|rb))", re.I)
LINE_PATTERN = re.compile(r"line\s+(\d+)", re.I)


@dataclass(slots=True)
class AffectedFile:
    path: str
    line: int | None = None
    content: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class FixContext:
    source_file: str
    source_line: int | None = None
    entity_name: str | None = None
    change_detail: str | None = None
    affected_files: list[AffectedFile] = field(default_factory=list)
    issue_description: str = ""

    @property
    def has_context(self) -> bool:
        return bool(self.entity_name or self.change_detail)


class ContextFetcher:
    def __init__(self, github: GitHubService):
        self.github = github

    async def fetch(
        self, owner: str, repo: str, ref: str,
        comment_body: str, source_file: str, source_line: int | None = None,
    ) -> FixContext:
        ctx = FixContext(
            source_file=source_file,
            source_line=source_line,
            issue_description=comment_body,
        )

        if match := ENTITY_PATTERN.search(comment_body):
            ctx.entity_name = match.group(1)
        for marker in ("Problem:", "Issue:"):
            if marker in comment_body:
                start = comment_body.find(marker) + len(marker)
                end = comment_body.find("\n", start)
                ctx.change_detail = comment_body[start:end].strip() if end > start else None
                break

        files = self._parse_files(comment_body, source_file)
        if files:
            ctx.affected_files = await self._batch_fetch(owner, repo, ref, files)

        log.info("context_fetcher.done", entity=ctx.entity_name, count=len(ctx.affected_files))
        return ctx

    def _parse_files(
        self, comment: str, source: str
    ) -> list[tuple[str, int | None, str | None]]:
        results, seen = [], {source}
        for line in comment.split("\n"):
            if match := FILE_PATTERN.search(line):
                path = match.group(1)
                if path not in seen:
                    seen.add(path)
                    line_num = int(m.group(1)) if (m := LINE_PATTERN.search(line)) else None
                    results.append((path, line_num, line.strip()))
        return results

    async def _batch_fetch(
        self, owner: str, repo: str, ref: str,
        files: list[tuple[str, int | None, str | None]],
    ) -> list[AffectedFile]:
        sem = asyncio.Semaphore(5)

        async def fetch_one(path: str, line: int | None, reason: str | None):
            async with sem:
                try:
                    content = await self.github.get_file_raw(owner, repo, path, ref)
                    if content:
                        return AffectedFile(path=path, line=line, content=content, reason=reason)
                except Exception:
                    pass
            return None

        results = await asyncio.gather(*[fetch_one(*f) for f in files])
        return [r for r in results if r]
