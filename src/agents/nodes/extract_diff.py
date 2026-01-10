"""Extract diff node - Phase 1 of the review pipeline.

Parses PR diff and identifies changed code units without using LLM.
This is a deterministic operation using AST analysis.
"""

import structlog

from ...analysis.ast_analyzer import get_ast_analyzer
from ...analysis.diff_extractor import ChangeType, DiffExtractor
from ...app.services.github import GitHubService
from ...core.config import ReviewerConfig
from ..state import ReviewState

log = structlog.get_logger()


async def run(state: ReviewState) -> dict:
    """Extract and analyze PR diff.
    
    Phase 1 of the 3-phase review pipeline:
    1. Fetch PR files from GitHub
    2. Parse diffs into structured format
    3. Extract changed functions using AST
    4. Identify new/deleted files
    
    This node does NOT use LLM - it's purely deterministic.
    
    Args:
        state: Current workflow state with pr_context.
        
    Returns:
        State updates with file_diffs, function_changes, etc.
    """
    ctx = state["pr_context"]
    config: ReviewerConfig = state.get("repo_config", ReviewerConfig())
    
    log.info(
        "extract_diff.started",
        owner=ctx.owner,
        repo=ctx.repo,
        pr=ctx.pr_number,
        base=ctx.base_branch,
        head=ctx.head_branch,
    )
    
    async with GitHubService(ctx.installation_id) as github:
        # Create diff extractor
        extractor = DiffExtractor(github)
        
        # Extract diffs from PR
        diffs = await extractor.extract(
            ctx.owner,
            ctx.repo,
            ctx.pr_number,
            ctx.base_branch,
            ctx.head_branch,
        )
        
        # Filter based on config
        filtered_diffs = [
            d for d in diffs
            if not config.should_ignore(d.file_path)
        ]
        
        # Check if PR should be skipped
        if not filtered_diffs:
            log.info("extract_diff.skipped", reason="no_relevant_files")
            return {
                "skip_review": True,
                "skip_reason": "No relevant files to review",
                "file_diffs": [],
                "function_changes": {},
                "new_files": [],
                "deleted_files": [],
            }
        
        # Analyze function changes using AST
        analyzer = get_ast_analyzer()
        function_changes: dict[str, dict] = {}
        new_files: list[str] = []
        deleted_files: list[str] = []
        
        for diff in filtered_diffs:
            match diff.status:
                case ChangeType.ADDED:
                    new_files.append(diff.file_path)
                    # Extract functions from new file
                    if diff.head_content:
                        funcs = analyzer.extract_functions(
                            diff.file_path, diff.head_content
                        )
                        for func in funcs:
                            function_changes[func.name] = {
                                "type": "added",
                                "new": func,
                            }
                
                case ChangeType.DELETED:
                    deleted_files.append(diff.file_path)
                    # Extract functions from deleted file
                    if diff.base_content:
                        funcs = analyzer.extract_functions(
                            diff.file_path, diff.base_content
                        )
                        for func in funcs:
                            function_changes[func.name] = {
                                "type": "deleted",
                                "old": func,
                            }
                
                case ChangeType.MODIFIED | ChangeType.RENAMED:
                    # Compare functions between versions
                    if diff.base_content and diff.head_content:
                        changes = analyzer.compare_functions(
                            diff.base_content,
                            diff.head_content,
                            diff.file_path,
                        )
                        function_changes.update(changes)
        
        log.info(
            "extract_diff.complete",
            files=len(filtered_diffs),
            functions_changed=len(function_changes),
            new_files=len(new_files),
            deleted_files=len(deleted_files),
        )
        
        return {
            "file_diffs": filtered_diffs,
            "function_changes": function_changes,
            "new_files": new_files,
            "deleted_files": deleted_files,
            "skip_review": False,
        }
