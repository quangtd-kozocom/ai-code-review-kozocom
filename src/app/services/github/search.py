"""GitHub Code Search operations."""

import structlog

from .client import GitHubClient

log = structlog.get_logger()


class SearchService(GitHubClient):
    """GitHub Code Search related operations.
    
    Provides access to GitHub's Code Search API for finding files
    that reference specific classes or methods.
    """

    async def search_code(
        self,
        query: str,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict]:
        """Search for code across a repository.
        
        Args:
            query: Search query (e.g., "PaymentService repo:owner/repo")
            per_page: Results per page (max 100)
            page: Page number
            
        Returns:
            List of search result items with path, repository, etc.
        """
        token = await self._get_token()
        
        resp = await self._request(
            "GET",
            f"{self.BASE_URL}/search/code",
            headers={
                **self._headers(token),
                "Accept": "application/vnd.github.text-match+json",
            },
            params={
                "q": query,
                "per_page": min(per_page, 100),
                "page": page,
            },
        )
        
        if resp.status_code == 422:
            log.warning("search_code.unprocessable", query=query)
            return []
        
        if resp.status_code == 403:
            log.warning("search_code.rate_limited", query=query)
            return []
        
        resp.raise_for_status()
        data = resp.json()
        
        items = data.get("items", [])
        log.debug(
            "search_code.complete",
            query=query,
            total_count=data.get("total_count", 0),
            items_returned=len(items),
        )
        
        return items
