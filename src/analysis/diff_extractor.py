"""Diff extraction from GitHub PR.

Parses GitHub PR diffs and extracts structured information about changes,
including changed functions, modified lines, and hunks.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Self

import structlog

log = structlog.get_logger()


class ChangeType(StrEnum):
    """Type of change to a code entity."""
    ADDED = auto()
    MODIFIED = auto()
    DELETED = auto()
    RENAMED = auto()


@dataclass(frozen=True, slots=True)
class DiffHunk:
    """A single hunk from a unified diff."""
    
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str
    
    @classmethod
    def from_header(cls, header: str, content: str) -> Self | None:
        """Parse hunk from diff header line.
        
        Format: @@ -old_start,old_count +new_start,new_count @@
        """
        pattern = r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
        if m := re.match(pattern, header):
            return cls(
                old_start=int(m[1]),
                old_count=int(m[2] or 1),
                new_start=int(m[3]),
                new_count=int(m[4] or 1),
                content=content,
            )
        return None


@dataclass(slots=True)
class FunctionChange:
    """Represents a changed function in the PR."""
    
    name: str
    file_path: str
    change_type: ChangeType
    old_code: str | None = None
    new_code: str | None = None
    old_signature: str | None = None
    new_signature: str | None = None
    line_range: tuple[int, int] = (0, 0)
    added_lines: list[int] = field(default_factory=list)
    deleted_lines: list[int] = field(default_factory=list)
    
    @property
    def is_signature_changed(self) -> bool:
        """Check if function signature was modified."""
        return self.old_signature != self.new_signature
    
    @property
    def change_size(self) -> int:
        """Calculate the size of the change."""
        return len(self.added_lines) + len(self.deleted_lines)


@dataclass(slots=True)
class FileDiff:
    """Structured diff information for a single file."""
    
    file_path: str
    status: ChangeType
    old_path: str | None = None  # For renames
    hunks: list[DiffHunk] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    patch: str = ""
    base_content: str | None = None
    head_content: str | None = None
    language: str | None = None
    
    @property
    def changed_line_numbers(self) -> set[int]:
        """Get all line numbers that were changed (in new file)."""
        lines: set[int] = set()
        for hunk in self.hunks:
            current_line = hunk.new_start
            for line in hunk.content.split("\n"):
                match line[:1]:
                    case "+":
                        lines.add(current_line)
                        current_line += 1
                    case "-":
                        pass  # Deleted lines don't exist in new file
                    case _:
                        current_line += 1
        return lines


class DiffExtractor:
    """Extract structured diff information from GitHub PR.
    
    This class handles parsing GitHub's PR diff format and extracting
    meaningful change information without needing vector database.
    """
    
    def __init__(self, github_client) -> None:
        """Initialize with GitHub client for API calls.
        
        Args:
            github_client: GitHub service instance for fetching data.
        """
        self._github = github_client
    
    async def extract(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        base_ref: str,
        head_ref: str,
    ) -> list[FileDiff]:
        """Extract diff information from a PR.
        
        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            base_ref: Base branch ref (target).
            head_ref: Head branch ref (source).
            
        Returns:
            List of FileDiff objects with parsed change information.
        """
        log.info(
            "diff_extractor.extracting",
            owner=owner,
            repo=repo,
            pr=pr_number,
            base=base_ref,
            head=head_ref,
        )
        
        # Fetch PR files from GitHub API
        pr_files = await self._github.get_pr_files(owner, repo, pr_number)
        
        diffs: list[FileDiff] = []
        for file_data in pr_files:
            diff = await self._extract_file_diff(
                owner, repo, file_data, base_ref, head_ref
            )
            if diff:
                diffs.append(diff)
        
        log.info(
            "diff_extractor.complete",
            files_count=len(diffs),
            total_additions=sum(d.additions for d in diffs),
            total_deletions=sum(d.deletions for d in diffs),
        )
        
        return diffs
    
    async def _extract_file_diff(
        self,
        owner: str,
        repo: str,
        file_data: dict,
        base_ref: str,
        head_ref: str,
    ) -> FileDiff | None:
        """Extract diff for a single file.
        
        Args:
            owner: Repository owner.
            repo: Repository name.
            file_data: GitHub file data from PR files endpoint.
            base_ref: Base branch ref.
            head_ref: Head branch ref.
            
        Returns:
            FileDiff object or None if file should be skipped.
        """
        file_path = file_data["filename"]
        status = self._map_status(file_data["status"])
        patch = file_data.get("patch", "")
        
        # Parse hunks from patch
        hunks = self._parse_patch(patch)
        
        # Detect language from extension
        language = self._detect_language(file_path)
        
        diff = FileDiff(
            file_path=file_path,
            status=status,
            old_path=file_data.get("previous_filename"),
            hunks=hunks,
            additions=file_data.get("additions", 0),
            deletions=file_data.get("deletions", 0),
            patch=patch,
            language=language,
        )
        
        # Fetch full content for both branches (for AST analysis)
        match status:
            case ChangeType.ADDED:
                diff.head_content = await self._fetch_content(
                    owner, repo, file_path, head_ref
                )
            case ChangeType.DELETED:
                diff.base_content = await self._fetch_content(
                    owner, repo, file_path, base_ref
                )
            case ChangeType.MODIFIED | ChangeType.RENAMED:
                # Fetch from both branches for comparison
                old_path = diff.old_path or file_path
                diff.base_content, diff.head_content = await self._fetch_both_contents(
                    owner, repo, old_path, file_path, base_ref, head_ref
                )
        
        return diff
    
    def _parse_patch(self, patch: str) -> list[DiffHunk]:
        """Parse unified diff patch into hunks.
        
        Args:
            patch: Git unified diff string.
            
        Returns:
            List of parsed DiffHunk objects.
        """
        if not patch:
            return []
        
        hunks: list[DiffHunk] = []
        current_header: str | None = None
        current_content: list[str] = []
        
        for line in patch.split("\n"):
            if line.startswith("@@"):
                # Save previous hunk
                if current_header:
                    if hunk := DiffHunk.from_header(
                        current_header, "\n".join(current_content)
                    ):
                        hunks.append(hunk)
                
                current_header = line
                current_content = []
            elif current_header:
                current_content.append(line)
        
        # Don't forget the last hunk
        if current_header:
            if hunk := DiffHunk.from_header(
                current_header, "\n".join(current_content)
            ):
                hunks.append(hunk)
        
        return hunks
    
    async def _fetch_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str | None:
        """Fetch file content at a specific ref."""
        try:
            return await self._github.get_file_raw(owner, repo, path, ref)
        except Exception as e:
            log.warning(
                "diff_extractor.fetch_failed",
                path=path,
                ref=ref,
                error=str(e),
            )
            return None
    
    async def _fetch_both_contents(
        self,
        owner: str,
        repo: str,
        old_path: str,
        new_path: str,
        base_ref: str,
        head_ref: str,
    ) -> tuple[str | None, str | None]:
        """Fetch file content from both base and head refs."""
        import asyncio
        
        base_task = self._fetch_content(owner, repo, old_path, base_ref)
        head_task = self._fetch_content(owner, repo, new_path, head_ref)
        
        base_content, head_content = await asyncio.gather(
            base_task, head_task, return_exceptions=True
        )
        
        return (
            base_content if isinstance(base_content, str) else None,
            head_content if isinstance(head_content, str) else None,
        )
    
    @staticmethod
    def _map_status(status: str) -> ChangeType:
        """Map GitHub status string to ChangeType enum."""
        match status:
            case "added":
                return ChangeType.ADDED
            case "removed":
                return ChangeType.DELETED
            case "renamed":
                return ChangeType.RENAMED
            case _:
                return ChangeType.MODIFIED
    
    @staticmethod
    def _detect_language(file_path: str) -> str | None:
        """Detect programming language from file extension."""
        from .models import detect_language
        return detect_language(file_path)
