"""Data models for GitHub publisher."""

from dataclasses import dataclass, field
from typing import Literal

from ...state import ReviewComment


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Result of filtering comments by diff validity."""

    valid: list[ReviewComment]
    skipped: list[ReviewComment]

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def has_valid(self) -> bool:
        return self.valid_count > 0

    @property
    def has_skipped(self) -> bool:
        return self.skipped_count > 0


@dataclass
class PublishResult:
    """Result of publishing a review to GitHub."""

    review_id: int | None = None
    errors: list[str] = field(default_factory=list)
    mode: Literal["review", "comment", "failed"] = "review"

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0 or self.mode != "failed"
