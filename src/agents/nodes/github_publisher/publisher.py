"""GitHub Review Publisher - main publishing logic."""

import structlog

from ....app.services.github import GitHubService
from ....core.i18n import Language
from ...state import PRContext, ReviewComment
from .formatter import CommentFormatter
from .models import FilterResult, PublishResult

log = structlog.get_logger()


class GitHubReviewPublisher:
    """Publishes code review comments to GitHub PRs."""

    def __init__(
        self,
        github: GitHubService,
        ctx: PRContext,
        language: Language = "en",
    ):
        self._github = github
        self._ctx = ctx
        self._formatter = CommentFormatter(language, ctx)

    async def publish(
        self,
        summary: str,
        comments: list[ReviewComment],
    ) -> PublishResult:
        """
        Publish review to GitHub.

        Returns PublishResult with review_id and any errors encountered.
        """
        log.info(
            "github_publisher.started",
            pr=self._ctx.pr_number,
            total_comments=len(comments),
        )

        if not comments:
            log.info("github_publisher.no_comments", pr=self._ctx.pr_number)
            return PublishResult(mode="comment")

        # In v2, all comments should be valid since they come from function review
        return await self._publish_as_review(summary, comments)

    def _log_filter_result(self, result: FilterResult) -> None:
        if result.has_skipped:
            log.warning(
                "github_publisher.comments_skipped",
                valid=result.valid_count,
                skipped=result.skipped_count,
            )

    def _build_final_summary(self, summary: str, result: FilterResult) -> str:
        if not result.has_skipped:
            return summary
        note = self._formatter.build_skipped_note(result.skipped_count)
        return f"{summary}\n\n---\n{note}"

    async def _publish_as_comment(self, body: str) -> PublishResult:
        """Fallback: post summary as issue comment when no valid inline comments."""
        log.warning("github_publisher.no_valid_comments", pr=self._ctx.pr_number)
        try:
            comment_id = await self._github.create_issue_comment(
                owner=self._ctx.owner,
                repo=self._ctx.repo,
                issue_number=self._ctx.pr_number,
                body=body,
            )
            log.info("github_publisher.posted_as_comment", comment_id=comment_id)
            return PublishResult(mode="comment")
        except Exception as e:
            log.exception("github_publisher.comment_failed")
            return PublishResult(errors=[str(e)], mode="failed")

    async def _publish_as_review(
        self,
        summary: str,
        comments: list[ReviewComment],
    ) -> PublishResult:
        """Post as full review with inline comments."""
        try:
            review_id = await self._post_review(summary, comments)
            log.info(
                "github_publisher.review_posted",
                review_id=review_id,
                pr=self._ctx.pr_number,
            )
            return PublishResult(review_id=review_id, mode="review")

        except Exception as e:
            log.exception("github_publisher.review_failed")
            return await self._fallback_to_comment(summary, comments, original_error=e)

    async def _fallback_to_comment(
        self,
        summary: str,
        comments: list[ReviewComment],
        original_error: Exception,
    ) -> PublishResult:
        """Try posting as issue comment when review fails."""
        log.info("github_publisher.fallback_attempt")
        try:
            fallback_body = self._formatter.format_fallback_body(summary, comments)
            comment_id = await self._github.create_issue_comment(
                owner=self._ctx.owner,
                repo=self._ctx.repo,
                issue_number=self._ctx.pr_number,
                body=fallback_body,
            )
            log.info("github_publisher.fallback_success", comment_id=comment_id)
            return PublishResult(
                errors=[f"Review failed: {original_error}"],
                mode="comment",
            )
        except Exception as fallback_error:
            log.exception("github_publisher.fallback_failed")
            return PublishResult(
                errors=[str(original_error), str(fallback_error)],
                mode="failed",
            )

    async def _post_review(
        self,
        summary: str,
        comments: list[ReviewComment],
    ) -> int:
        """Post review to GitHub."""
        return await self._github.create_review(
            owner=self._ctx.owner,
            repo=self._ctx.repo,
            pr_number=self._ctx.pr_number,
            body=summary,
            comments=self._build_review_payload(comments),
            event=self._determine_review_event(comments),
        )

    def _build_review_payload(self, comments: list[ReviewComment]) -> list[dict]:
        return [
            {
                "path": c.file,
                "line": c.line,
                "body": self._formatter.format_inline(c),
            }
            for c in comments
        ]

    @staticmethod
    def _determine_review_event(comments: list[ReviewComment]) -> str:
        has_critical = any(c.severity == "critical" for c in comments)
        return "REQUEST_CHANGES" if has_critical else "COMMENT"
