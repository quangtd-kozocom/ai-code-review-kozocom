# 04. Integration Plan

## 🎯 Mục tiêu

Integrate RAG context vào existing review flow với **minimal changes** đến code hiện tại.

---

## 📋 Files cần modify

| File                                    | Type   | Changes                       |
| --------------------------------------- | ------ | ----------------------------- |
| `src/app/api/v1/webhooks.py`            | Modify | Handle `installation` events  |
| `src/workers/tasks.py`                  | Modify | Add indexing tasks            |
| `src/agents/nodes/context_extractor.py` | Modify | Add RAG retrieval             |
| `src/agents/state.py`                   | Modify | Extend state with RAG context |
| `src/agents/prompts/*.py`               | Modify | Add context sections          |
| `pyproject.toml`                        | Modify | Add dependencies              |
| `.env.example`                          | Modify | Add Pinecone config           |

---

## 🔄 Integration Points

### 1. Webhook Handler - Installation Events

```python
# src/app/api/v1/webhooks.py

# THÊM MỚI: Handle installation events
@router.post("/github")
async def github_webhook(request: Request):
    payload = await parse_webhook(request)
    event = request.headers.get("X-GitHub-Event")

    # EXISTING: Handle pull_request
    if event == "pull_request":
        # ... existing logic ...
        pass

    # NEW: Handle installation
    elif event == "installation":
        if payload.get("action") == "created":
            # Queue indexing task
            from src.workers.tasks import index_installation
            index_installation.delay(
                installation_id=payload["installation"]["id"],
                repositories=[r["full_name"] for r in payload.get("repositories", [])]
            )
            return {"status": "indexing_queued"}

    # NEW: Handle PR merge (for incremental updates)
    elif event == "pull_request" and payload.get("action") == "closed":
        if payload["pull_request"].get("merged"):
            from src.workers.tasks import update_rag_index
            update_rag_index.delay(
                owner=payload["repository"]["owner"]["login"],
                repo=payload["repository"]["name"],
                pr_number=payload["pull_request"]["number"],
            )
```

---

### 2. Celery Tasks - Indexing

```python
# src/workers/tasks.py

# THÊM MỚI: Import RAG modules
from src.rag.indexer import create_indexer
from src.app.services.github import GitHubService

# THÊM MỚI: Indexing task
@celery_app.task(bind=True, max_retries=3)
def index_installation(self, installation_id: int, repositories: list[str]):
    """Index all repositories for an installation."""
    try:
        github = GitHubService()
        indexer = create_indexer(github)

        for repo_full_name in repositories:
            owner, repo = repo_full_name.split("/")

            # Use Redis lock to prevent concurrent indexing
            lock_key = f"rag:index:{owner}/{repo}"
            with redis_client.lock(lock_key, timeout=600):
                stats = asyncio.run(
                    indexer.index_repository(
                        owner=owner,
                        repo=repo,
                        installation_id=installation_id,
                    )
                )
                logger.info(f"Indexed {repo_full_name}: {stats}")

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def update_rag_index(self, owner: str, repo: str, pr_number: int):
    """Incrementally update RAG index after PR merge."""
    try:
        github = GitHubService()
        indexer = create_indexer(github)

        # Get PR files
        files = asyncio.run(github.get_pr_files(owner, repo, pr_number))

        # Fetch content for added/modified files
        files_with_content = []
        for file in files:
            if file["status"] in ("added", "modified"):
                content = asyncio.run(
                    github.get_file_content(owner, repo, file["filename"])
                )
                files_with_content.append({
                    "filename": file["filename"],
                    "status": file["status"],
                    "content": content,
                })
            else:
                files_with_content.append({
                    "filename": file["filename"],
                    "status": file["status"],
                })

        # Update index
        lock_key = f"rag:index:{owner}/{repo}"
        with redis_client.lock(lock_key, timeout=300):
            stats = asyncio.run(
                indexer.update_files(owner, repo, files_with_content)
            )
            logger.info(f"Updated index {owner}/{repo}: {stats}")

    except Exception as e:
        logger.error(f"Index update failed: {e}")
        raise self.retry(exc=e, countdown=30)
```

---

### 3. Context Extractor - Add RAG Retrieval

```python
# src/agents/nodes/context_extractor.py

# BEFORE (simplified):
class ContextExtractor:
    async def extract(self, pr_data: dict) -> list[FileChange]:
        files = await self.github.get_pr_files(...)
        return [FileChange(f["filename"], f["patch"]) for f in files]


# AFTER:
from src.ast.parser import code_parser
from src.rag.retriever import retriever


class ContextExtractor:
    async def extract(self, pr_data: dict) -> list[EnhancedFileChange]:
        """Extract context with AST and RAG enrichment."""
        owner = pr_data["owner"]
        repo = pr_data["repo"]
        files = await self.github.get_pr_files(...)

        enhanced_files = []
        for file in files:
            filename = file["filename"]
            patch = file.get("patch", "")
            status = file["status"]

            # Initialize enriched data
            ast_info = None
            related_context = []
            full_content = None

            # Fetch full content for new files or if needed for AST
            if status == "added":
                full_content = await self.github.get_file_content(
                    owner, repo, filename, ref=pr_data["head_sha"]
                )

            # Parse AST if we have content or can get it
            if full_content or status == "modified":
                content = full_content or await self.github.get_file_content(
                    owner, repo, filename, ref=pr_data["head_sha"]
                )
                if content:
                    ast_info = code_parser.get_ast_info(filename, content)

            # RAG retrieval only for modified files (they exist in index)
            if status == "modified" and ast_info:
                # Get changed function names from AST + diff
                changed_entities = self._identify_changed_entities(ast_info, patch)

                for entity in changed_entities:
                    context = retriever.retrieve_for_function(
                        owner=owner,
                        repo=repo,
                        function_name=entity["name"],
                        signature=entity.get("signature"),
                        current_file=filename,
                    )
                    related_context.extend(context)

            enhanced_files.append(EnhancedFileChange(
                filename=filename,
                patch=patch,
                full_content=full_content,
                ast_info=ast_info,
                related_context=related_context,
            ))

        return enhanced_files

    def _identify_changed_entities(self, ast_info, patch: str) -> list[dict]:
        """Identify which functions/classes were changed based on diff lines."""
        changed = []

        # Parse diff to get changed line numbers
        changed_lines = self._parse_diff_lines(patch)

        # Check which functions contain changed lines
        for func in ast_info.functions:
            if any(func["start_line"] <= line <= func["end_line"]
                   for line in changed_lines):
                changed.append(func)

        return changed

    def _parse_diff_lines(self, patch: str) -> list[int]:
        """Extract line numbers from diff patch."""
        import re
        lines = []

        # Parse @@ -start,count +start,count @@ format
        for match in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
            start = int(match.group(1))
            count = int(match.group(2) or 1)
            lines.extend(range(start, start + count))

        return lines
```

---

### 4. Agent State - Extend with RAG Context

````python
# src/agents/state.py

# BEFORE:
@dataclass
class FileChange:
    filename: str
    patch: str


# AFTER:
from src.ast.models import ASTInfo, RelatedCode


@dataclass
class EnhancedFileChange:
    """File change with enriched context."""
    filename: str
    patch: str
    full_content: str | None = None
    ast_info: ASTInfo | None = None
    related_context: list[RelatedCode] = field(default_factory=list)

    def format_for_prompt(self) -> str:
        """Format file change for LLM prompt."""
        parts = [
            f"## File: {self.filename}",
            "",
            "### Diff:",
            "```",
            self.patch,
            "```",
        ]

        # Add AST info if available
        if self.ast_info:
            parts.extend([
                "",
                "### Code Structure:",
                f"- Functions: {', '.join(f['name'] for f in self.ast_info.functions)}",
                f"- Classes: {', '.join(c['name'] for c in self.ast_info.classes)}",
            ])

        # Add related context if available
        if self.related_context:
            parts.extend([
                "",
                "### Related Code from Codebase:",
            ])
            for ctx in self.related_context[:3]:  # Limit to top 3
                parts.extend([
                    f"",
                    f"**{ctx.relationship.upper()}**: `{ctx.file_path}` - `{ctx.name}`",
                    "```",
                    ctx.content[:500],  # Truncate
                    "```",
                ])

        return "\n".join(parts)
````

---

### 5. Agent Prompts - Add Context Sections

```python
# src/agents/prompts/logic.py

# BEFORE:
LOGIC_PROMPT = """
You are a code review expert focusing on logic issues.

Review the following code changes:
{file_changes}
"""

# AFTER:
LOGIC_PROMPT = """
You are a code review expert focusing on logic issues.

## Code Changes to Review:
{file_changes}

## Analysis Guidelines:

When reviewing, consider:
1. The code structure shown in "Code Structure" section
2. How this code interacts with "Related Code from Codebase"
3. Whether changes are consistent with existing patterns

Focus on:
- Logic errors and edge cases
- Inconsistencies with related code
- Breaking changes that might affect callers
"""
```

---

## 📊 Phased Rollout

### Phase 1: Basic Integration (Week 1)

```
✅ Add dependencies
✅ Implement AST parsing
✅ Implement embedder + vector store
✅ Add indexing tasks
✅ Handle installation webhook
```

### Phase 2: Review Enhancement (Week 2)

```
✅ Modify context_extractor
✅ Update prompts
✅ Test end-to-end flow
```

### Phase 3: Incremental Updates (Week 3)

```
✅ Handle PR merge → update index
✅ Add concurrency locks
✅ Add error handling / retries
```

### Phase 4: Monitoring & Optimization (Week 4)

```
✅ Add metrics (indexing time, retrieval latency)
✅ Tune retrieval parameters
✅ Handle edge cases (large repos, rate limits)
```

---

## ⚠️ Error Handling Strategy

```python
# Graceful degradation: If RAG fails, continue with basic review

class ContextExtractor:
    async def extract(self, pr_data: dict) -> list[EnhancedFileChange]:
        files = await self.github.get_pr_files(...)

        enhanced_files = []
        for file in files:
            # Basic info (always available)
            filename = file["filename"]
            patch = file.get("patch", "")

            # Enhanced info (may fail gracefully)
            ast_info = None
            related_context = []

            try:
                ast_info = self._get_ast_info(file)
            except Exception as e:
                logger.warning(f"AST parsing failed for {filename}: {e}")

            try:
                if ast_info:
                    related_context = self._get_related_context(file, ast_info)
            except Exception as e:
                logger.warning(f"RAG retrieval failed for {filename}: {e}")

            enhanced_files.append(EnhancedFileChange(
                filename=filename,
                patch=patch,
                ast_info=ast_info,
                related_context=related_context,
            ))

        return enhanced_files
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
# tests/test_ast_parser.py
def test_parse_python_function():
    content = '''
def calculate_total(items, discount=0):
    """Calculate total price."""
    return sum(i.price for i in items) * (1 - discount)
'''
    parser = CodeParser()
    chunks = parser.parse_file("test.py", content)

    assert len(chunks) == 1
    assert chunks[0].name == "calculate_total"
    assert chunks[0].chunk_type == "function"


# tests/test_retriever.py
def test_retrieve_related_code(mock_pinecone):
    mock_pinecone.query.return_value = MockResults([...])

    results = retriever.retrieve("owner", "repo", "calculate_total")

    assert len(results) > 0
    assert all(isinstance(r, RelatedCode) for r in results)
```

### Integration Tests

```python
# tests/test_rag_integration.py
@pytest.mark.integration
async def test_full_indexing_flow():
    # Use a small test repo
    indexer = create_indexer(mock_github)
    stats = await indexer.index_repository("test-owner", "test-repo")

    assert stats["files_processed"] > 0
    assert stats["chunks_created"] > 0
```

---

## 📈 Success Metrics

| Metric                   | Target  | How to Measure        |
| ------------------------ | ------- | --------------------- |
| Indexing success rate    | > 95%   | Monitor task failures |
| Retrieval latency        | < 500ms | Measure query time    |
| Context relevance        | > 70%   | Manual evaluation     |
| False positive reduction | > 30%   | Compare before/after  |

---

## 🔜 Post-Implementation

Sau khi implement xong, cần:

1. **Documentation**: Update README với RAG feature
2. **Configuration guide**: Pinecone setup instructions
3. **Monitoring dashboard**: Track indexing status per repo
4. **User feedback loop**: Collect feedback on context quality
