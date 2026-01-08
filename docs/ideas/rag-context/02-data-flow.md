# 02. Data Flow & Lifecycle

## 📊 RAG Lifecycle Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RAG LIFECYCLE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: Installation (one-time)                                           │
│  ────────────────────────────────                                           │
│  User installs GitHub App                                                   │
│         │                                                                   │
│         ▼                                                                   │
│  Webhook: installation.created                                              │
│         │                                                                   │
│         ▼                                                                   │
│  Celery Task: index_installation                                            │
│         │                                                                   │
│         ├──▶ For each repo: clone → parse → embed → store                  │
│         │                                                                   │
│         ▼                                                                   │
│  ✅ Ready for context-aware reviews                                        │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  PHASE 2: Review (per PR)                                                   │
│  ────────────────────────                                                   │
│  PR opened/updated                                                          │
│         │                                                                   │
│         ▼                                                                   │
│  Webhook: pull_request.opened/synchronize                                   │
│         │                                                                   │
│         ▼                                                                   │
│  Build context:                                                             │
│  • Fetch diff (existing)                                                    │
│  • Fetch full content for new files                                        │
│  • Parse AST (new)                                                          │
│  • Query RAG for related code (new)                                        │
│         │                                                                   │
│         ▼                                                                   │
│  Send to agents with enhanced context                                       │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  PHASE 3: Update (after merge)                                              │
│  ─────────────────────────────                                              │
│  PR merged                                                                  │
│         │                                                                   │
│         ▼                                                                   │
│  Webhook: pull_request.closed (merged=true)                                 │
│         │                                                                   │
│         ▼                                                                   │
│  Incremental update:                                                        │
│  • Add new files                                                            │
│  • Update modified files                                                    │
│  • Remove deleted files                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flow 1: Initial Indexing (On Installation)

### Trigger

```python
# Webhook payload
{
    "action": "created",
    "installation": {
        "id": 12345,
        "account": {"login": "acme-corp"}
    },
    "repositories": [
        {"full_name": "acme-corp/backend-api"},
        {"full_name": "acme-corp/frontend-app"}
    ]
}
```

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INITIAL INDEXING FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. Webhook Handler                                                        │
│      │                                                                      │
│      ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  Validate webhook signature                                          │  │
│   │  Extract installation_id, repositories list                          │  │
│   │  Queue Celery task: index_installation.delay(installation_id)        │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│      │                                                                      │
│      ▼                                                                      │
│   2. Celery Task: index_installation                                        │
│      │                                                                      │
│      ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  For each repository:                                                │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  a. Clone repo (shallow, default branch)                    │    │  │
│   │  │     git clone --depth 1 https://x-access-token:XXX@...      │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  b. Walk files (skip ignored patterns)                      │    │  │
│   │  │     • Skip: node_modules, .venv, dist, .git, .env*          │    │  │
│   │  │     • Include: .py, .js, .ts, .php, .go, .md, etc.          │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  c. For each file:                                          │    │  │
│   │  │     • Detect language                                       │    │  │
│   │  │     • Parse with Tree-sitter → CodeChunks                   │    │  │
│   │  │     • Check for secrets (skip if found)                     │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  d. Batch embed chunks                                      │    │  │
│   │  │     • Group into batches of 100                             │    │  │
│   │  │     • Call OpenAI embeddings API                            │    │  │
│   │  │     • Retry with exponential backoff                        │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  e. Upsert to Pinecone                                      │    │  │
│   │  │     • Namespace: f"{owner}/{repo}"                          │    │  │
│   │  │     • Batch upsert (100 vectors/call)                       │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │  ┌─────────────────────────────────────────────────────────────┐    │  │
│   │  │  f. Cleanup                                                 │    │  │
│   │  │     • Delete cloned repo from temp                          │    │  │
│   │  │     • Update DB: installation.indexed = true                │    │  │
│   │  └─────────────────────────────────────────────────────────────┘    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Estimated Time

| Repo Size | Files | Est. Time |
| --------- | ----- | --------- |
| 10K LOC   | ~100  | 1-2 min   |
| 100K LOC  | ~1000 | 5-10 min  |
| 500K LOC  | ~5000 | 20-30 min |

**Bottleneck**: Embedding API calls (rate limited)

---

## 🔄 Flow 2: PR Review (With RAG Context)

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PR REVIEW FLOW (ENHANCED)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Webhook: pull_request.opened                                              │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  1. Fetch PR files (existing logic)                                  │  │
│   │     • GET /repos/{owner}/{repo}/pulls/{pr}/files                    │  │
│   │     • Returns: filename, status, patch, etc.                        │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  2. For each file: Determine context strategy                        │  │
│   │                                                                      │  │
│   │     IF file.status == "added" (new file):                           │  │
│   │     ├── Fetch full content from PR branch                           │  │
│   │     ├── Parse AST → extract function/class names                    │  │
│   │     └── NO RAG query (file doesn't exist in index)                  │  │
│   │                                                                      │  │
│   │     IF file.status == "modified":                                    │  │
│   │     ├── Fetch full content                                          │  │
│   │     ├── Parse AST → identify CHANGED functions/classes              │  │
│   │     └── RAG query: find related code (callers, tests, similar)      │  │
│   │                                                                      │  │
│   │     IF file.status == "removed":                                     │  │
│   │     └── Note for post-merge cleanup (no review needed)              │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  3. Parse AST with Tree-sitter                                       │  │
│   │                                                                      │  │
│   │     Input: Full file content                                        │  │
│   │     Output: ASTInfo {                                                │  │
│   │       functions: [{name, signature, start_line, end_line}],         │  │
│   │       classes: [{name, methods}],                                   │  │
│   │       imports: ["os", "OrderService"],                              │  │
│   │       changed_entities: ["calculate_total"] ← from diff lines       │  │
│   │     }                                                                │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  4. RAG Retrieval                                                    │  │
│   │                                                                      │  │
│   │     Query construction:                                              │  │
│   │     • "calculate_total function with items and discount params"     │  │
│   │     • Include: signature, docstring                                 │  │
│   │                                                                      │  │
│   │     Pinecone query:                                                  │  │
│   │     • Namespace: "{owner}/{repo}"                                   │  │
│   │     • top_k: 5                                                       │  │
│   │     • Filter: exclude current file                                  │  │
│   │                                                                      │  │
│   │     Results processing:                                              │  │
│   │     • Categorize: callers, tests, similar code                      │  │
│   │     • Truncate if too long (token limit)                            │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  5. Build EnhancedFileChange                                         │  │
│   │                                                                      │  │
│   │     EnhancedFileChange {                                             │  │
│   │       filename: "src/services/order.py",                            │  │
│   │       patch: "@@ -10,5 +10,8 @@...",                                │  │
│   │       full_content: "..." (for new files),                          │  │
│   │       ast_info: ASTInfo {...},                                       │  │
│   │       related_context: [                                             │  │
│   │         {file: "tests/test_order.py", relationship: "test"},        │  │
│   │         {file: "api/checkout.py", relationship: "caller"}           │  │
│   │       ]                                                              │  │
│   │     }                                                                │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  6. Send to Agents (existing flow, enhanced prompts)                 │  │
│   │                                                                      │  │
│   │     Prompt now includes:                                             │  │
│   │     • Original diff                                                  │  │
│   │     • AST info (structured)                                          │  │
│   │     • Related code context                                           │  │
│   │                                                                      │  │
│   │     ──▶ Security Agent                                              │  │
│   │     ──▶ Logic Agent                                                 │  │
│   │     ──▶ Style Agent                                                 │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flow 3: Incremental Update (After Merge)

### Trigger

```python
# Webhook payload
{
    "action": "closed",
    "pull_request": {
        "merged": true,
        "number": 42,
        "base": {"ref": "main"}
    }
}
```

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INCREMENTAL UPDATE FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Webhook: pull_request.closed (merged=true)                                │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  1. Get PR files                                                     │  │
│   │     GET /repos/{owner}/{repo}/pulls/{pr}/files                      │  │
│   │     Returns: [{filename, status: added|modified|removed}]           │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  2. Queue Celery task: update_rag_index                              │  │
│   │     • Pass: owner, repo, files list                                 │  │
│   │     • Use lock to prevent concurrent updates                        │  │
│   └──────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  3. For each file by status:                                         │  │
│   │                                                                      │  │
│   │     status == "added":                                               │  │
│   │     ├── Fetch content from main branch                              │  │
│   │     ├── Parse → Embed → Upsert to Pinecone                          │  │
│   │     └── Result: New vectors added                                   │  │
│   │                                                                      │  │
│   │     status == "modified":                                            │  │
│   │     ├── Delete old vectors for this file                            │  │
│   │     ├── Fetch new content                                           │  │
│   │     ├── Parse → Embed → Upsert                                      │  │
│   │     └── Result: Vectors replaced                                    │  │
│   │                                                                      │  │
│   │     status == "removed":                                             │  │
│   │     ├── Delete vectors với metadata.file_path == filename           │  │
│   │     └── Result: Vectors removed                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   Note: Không cần clone cả repo, chỉ fetch từng file qua GitHub API        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Concurrency Handling

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONCURRENCY CONTROL                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Problem: Multiple events can trigger updates to same repo simultaneously   │
│                                                                              │
│  ┌───────────────┐     ┌───────────────┐                                    │
│  │ PR #1 merged  │     │ PR #2 merged  │                                    │
│  │ (same repo)   │     │ (same repo)   │                                    │
│  └───────┬───────┘     └───────┬───────┘                                    │
│          │                     │                                            │
│          │     ┌───────────────┘                                            │
│          ▼     ▼                                                            │
│      ┌───────────────────────────────┐                                      │
│      │  Redis Lock: rag:lock:{repo}  │                                      │
│      │  TTL: 300 seconds             │                                      │
│      └───────────────────────────────┘                                      │
│             │                │                                              │
│             ▼                ▼                                              │
│      [Acquired]        [Wait/Retry]                                         │
│             │                │                                              │
│             ▼                │                                              │
│      [Process update]        │                                              │
│             │                │                                              │
│             ▼                │                                              │
│      [Release lock] ────────▶│                                              │
│                              ▼                                              │
│                        [Acquire & Process]                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔜 Next: Implementation Draft

Xem [03-implementation-draft.md](./03-implementation-draft.md) để xem draft code.
