# 06. Implementation Checklist

Tài liệu này hướng dẫn **thứ tự implement** và **cách verify** từng bước.

---

## 📋 Pre-requisites

Trước khi bắt đầu, đảm bảo đã có:

- [ ] Pinecone account + API key (free tier)
- [ ] OpenAI API key (cho embeddings)
- [ ] Hiểu project structure hiện tại

---

## 🔢 Implementation Order

### Phase 1: Dependencies & Config (30 min)

```
Step 1.1: Add dependencies
──────────────────────────
File: pyproject.toml

Thêm:
"pinecone>=5.0.0",
"tree-sitter>=0.23.0",
"tree-sitter-languages>=1.10.0",
"gitpython>=3.1.0",

Verify: uv sync thành công
```

```
Step 1.2: Add environment variables
───────────────────────────────────
File: .env.example

Thêm:
PINECONE_API_KEY=pcsk_xxx
PINECONE_INDEX_NAME=code-reviewer

Verify: Copy sang .env và điền giá trị thật
```

```
Step 1.3: Create RAG config
───────────────────────────
File: src/rag/config.py

Tạo mới theo draft trong 03-implementation-draft.md

Verify: Import không lỗi
  python -c "from src.rag.config import get_rag_settings; print(get_rag_settings())"
```

---

### Phase 2: AST Module (1-2 hours)

```
Step 2.1: Create AST models
───────────────────────────
File: src/ast/__init__.py (empty)
File: src/ast/models.py

Tạo: CodeChunk, ASTInfo, RelatedCode dataclasses

Verify: Import OK
  python -c "from src.ast.models import CodeChunk"
```

```
Step 2.2: Create AST parser
───────────────────────────
File: src/ast/parser.py

Tạo: CodeParser class với methods:
- detect_language()
- parse_file()
- get_ast_info()

Verify: Parse sample file
  python -c "
  from src.ast.parser import get_code_parser
  parser = get_code_parser()
  chunks = parser.parse_file('test.py', 'def foo(): pass')
  print(f'Found {len(chunks)} chunks')
  "
```

---

### Phase 3: RAG Module - Core (2-3 hours)

```
Step 3.1: Create embedder
─────────────────────────
File: src/rag/__init__.py (empty)
File: src/rag/embedder.py

Tạo: Embedder class với methods:
- embed(texts: list[str])
- embed_single(text: str)

Verify: Embed sample text
  python -c "
  from src.rag.embedder import get_embedder
  embedder = get_embedder()
  vec = embedder.embed_single('def hello(): pass')
  print(f'Vector dimension: {len(vec)}')  # Should be 1024
  "
```

```
Step 3.2: Create vector store
─────────────────────────────
File: src/rag/vector_store.py

Tạo: VectorStore class với methods:
- upsert(vectors, namespace)
- query(vector, namespace, top_k)
- delete_by_file(namespace, file_path)
- delete_namespace(namespace)

Verify: Connect to Pinecone
  python -c "
  from src.rag.vector_store import get_vector_store
  store = get_vector_store()
  print(f'Index: {store.index_name}')
  "
```

```
Step 3.3: Create chunker
────────────────────────
File: src/rag/chunker.py

Tạo: Chunker class với methods:
- should_process_file(file_path)
- has_secrets(content)
- chunk_file(file_path, content)

Verify: Chunk sample file
  python -c "
  from src.rag.chunker import get_chunker
  chunker = get_chunker()
  chunks = chunker.chunk_file('test.py', 'class Foo:\n  def bar(self): pass')
  print(f'Chunks: {len(chunks)}')
  "
```

---

### Phase 4: RAG Module - Orchestration (2-3 hours)

```
Step 4.1: Create indexer
────────────────────────
File: src/rag/indexer.py

Tạo: Indexer class với methods:
- index_repository(owner, repo, branch, installation_id)
- update_files(owner, repo, files)

Verify: (Manual test với real repo later)
```

```
Step 4.2: Create retriever
──────────────────────────
File: src/rag/retriever.py

Tạo: Retriever class với methods:
- retrieve(owner, repo, query, exclude_file, top_k)
- retrieve_for_function(owner, repo, function_name, signature, current_file)

Verify: (Need indexed data to test)
```

---

### Phase 5: Integration (2-3 hours)

```
Step 5.1: Add Celery tasks
──────────────────────────
File: src/workers/tasks.py

Thêm:
- index_installation(installation_id, repositories)
- update_rag_index(owner, repo, pr_number)

Verify: Tasks registered
  celery -A src.workers.celery_app inspect registered
```

```
Step 5.2: Update webhook handler
────────────────────────────────
File: src/app/api/v1/webhooks.py

Thêm:
- Handle installation.created → queue index_installation
- Handle pull_request.closed (merged) → queue update_rag_index

Verify: (Test với ngrok + GitHub)
```

```
Step 5.3: Update context extractor
──────────────────────────────────
File: src/agents/nodes/context_extractor.py

Modify:
- Add AST parsing for files
- Add RAG retrieval for related context
- Return EnhancedFileChange instead of FileChange

Verify: (End-to-end test)
```

```
Step 5.4: Update agent prompts
──────────────────────────────
Files: src/agents/prompts/*.py

Modify:
- Add sections for AST info
- Add sections for related context

Verify: Review prompts manually
```

---

## ✅ Verification Checklist

### Unit Tests

```bash
# Run after each phase
pytest tests/test_ast_parser.py -v
pytest tests/test_rag_embedder.py -v
pytest tests/test_rag_chunker.py -v
pytest tests/test_rag_retriever.py -v
```

### Unit Test Examples

```python
# tests/test_ast_parser.py
import pytest
from src.ast.parser import get_code_parser
from src.ast.models import CodeChunk


class TestCodeParser:
    def test_parse_python_function(self):
        content = '''
def calculate_total(items, discount=0):
    """Calculate total price."""
    return sum(i.price for i in items) * (1 - discount)
'''
        parser = get_code_parser()
        chunks = parser.parse_file("test.py", content)

        assert len(chunks) == 1
        assert chunks[0].name == "calculate_total"
        assert chunks[0].chunk_type == "function"


# tests/test_rag_retriever.py
import pytest
from unittest.mock import MagicMock, patch
from src.rag.retriever import get_retriever
from src.ast.models import RelatedCode


class TestRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_related_code(self):
        with patch("src.rag.retriever.get_vector_store") as mock_store:
            mock_store.return_value.query.return_value = [
                {
                    "id": "test.py:foo:1",
                    "score": 0.9,
                    "metadata": {
                        "file_path": "test.py",
                        "name": "foo",
                        "content": "def foo(): pass",
                        "chunk_type": "function",
                    },
                }
            ]

            retriever = get_retriever()
            results = retriever.retrieve("owner", "repo", "calculate_total")

            assert len(results) > 0
            assert all(isinstance(r, RelatedCode) for r in results)
```

### Integration Test

```bash
# Test full indexing flow (needs real Pinecone)
python -c "
import asyncio
from src.rag.indexer import create_indexer
from src.app.services.github import GitHubService

async def test():
    # Note: GitHubService requires installation_id for authenticated requests
    github = GitHubService(installation_id=12345)  # Use your installation ID
    indexer = create_indexer(github)
    # Use a small public repo for testing
    stats = await indexer.index_repository('octocat', 'Hello-World')
    print(f'Indexed: {stats}')

asyncio.run(test())
"
```

### End-to-End Test

1. Install app on test repo
2. Check Celery logs: "Indexed {repo}"
3. Create PR
4. Check review comments include related context
5. Merge PR
6. Check Celery logs: "Updated index"

---

## 🚨 Common Issues & Solutions

### Issue 1: Pinecone index không tồn tại

```
Error: Index 'code-reviewer' not found
Solution: Index sẽ được tạo tự động khi upsert lần đầu
         Hoặc tạo manual trên Pinecone console
```

### Issue 2: Tree-sitter parse fail

```
Error: Language not supported
Solution: Check file extension in LANGUAGE_MAP
         Add new mappings if needed
```

### Issue 3: Embedding rate limit

```
Error: Rate limit exceeded
Solution: Add retry with exponential backoff
         Batch requests (100 at a time)
```

### Issue 4: Clone authentication fail

```
Error: Authentication failed
Solution: Check installation_id is correct
         Verify GitHub App permissions include Contents: Read
```

---

## 📊 Success Criteria

| Metric                              | Target    | How to Measure           |
| ----------------------------------- | --------- | ------------------------ |
| All unit tests pass                 | 100%      | `pytest`                 |
| Installation webhook → index starts | Works     | Check Celery logs        |
| PR review includes related context  | Works     | Review PR comment        |
| Merge → incremental update          | Works     | Check Pinecone namespace |
| No secrets indexed                  | 0 secrets | Manual check             |

---

## 🔜 After Implementation

1. **Documentation**: Update README.md với RAG feature
2. **Monitoring**: Add metrics cho indexing time, retrieval latency
3. **Error alerts**: Setup Sentry alerts cho indexing failures
