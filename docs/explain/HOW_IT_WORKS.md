# 🤖 AI Code Reviewer - Cách Hệ Thống Hoạt Động

## Tổng Quan

Hệ thống AI Code Reviewer tự động review Pull Request (PR) trên GitHub sử dụng 3 AI agents chuyên biệt. Khi có PR mới, hệ thống sẽ phân tích code và post comments trực tiếp lên GitHub.

---

## 🔄 Luồng Xử Lý (End-to-End Flow)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           LUỒNG CHÍNH                                    │
└──────────────────────────────────────────────────────────────────────────┘

1. Developer tạo/update PR trên GitHub
                    │
                    ▼
2. GitHub gửi Webhook ──────────────────────────────────────────┐
                    │                                           │
                    ▼                                           │
3. FastAPI nhận webhook (/api/v1/webhooks/github)               │
   └── Verify HMAC-SHA256 signature                             │
   └── Parse payload (PR number, repo, action)                  │
                    │                                           │
                    ▼                                           │
4. Queue task vào Celery (background)                           │
   └── Trả về ngay 200 OK cho GitHub                            │
                    │                                           │
                    ▼                                           │
5. Celery Worker xử lý task                                     │
   └── Chạy LangGraph workflow                                  │
                    │                                           │
    ┌───────────────┼───────────────────────────────┐           │
    │               │                               │           │
    ▼               ▼                               ▼           │
┌────────┐    ┌────────┐                      ┌────────┐        │
│Security│    │ Style  │                      │ Logic  │        │
│ Agent  │    │ Agent  │   (chạy song song)   │ Agent  │        │
└────┬───┘    └────┬───┘                      └────┬───┘        │
    │               │                               │           │
    └───────────────┴───────────────────────────────┘           │
                    │                                           │
                    ▼                                           │
6. Aggregator                                                   │
   └── Deduplicate comments                                     │
   └── Sort by severity                                         │
   └── Limit per file                                           │
                    │                                           │
                    ▼                                           │
7. GitHub Publisher                                             │
   └── Format comments                                          │
   └── POST review via GitHub API ──────────────────────────────┘
                    │
                    ▼
8. Slack Reporter (optional)
   └── Gửi notification về review
```

---

## 📦 Các Thành Phần Chính

### 1. Webhook Handler (`src/app/api/v1/webhooks.py`)

**Nhiệm vụ:** Nhận webhook từ GitHub, validate signature, queue task.

```python
# Signature verification (bảo mật quan trọng!)
expected = "sha256=" + hmac.new(secret, body, sha256).hexdigest()
hmac.compare_digest(expected, signature)  # Timing-safe comparison
```

**Events được xử lý:**

- `pull_request.opened` - PR mới được tạo
- `pull_request.synchronize` - PR được update (push thêm commits)
- `pull_request.reopened` - PR được mở lại

### 2. LangGraph Workflow (`src/agents/graph.py`)

**Nhiệm vụ:** Orchestrate 3 agents, aggregate results.

```
                    ┌──────────┐
                    │ Extract  │  (fetch PR files từ GitHub)
                    └────┬─────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │Security │    │  Style  │    │  Logic  │
    └────┬────┘    └────┬────┘    └────┬────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                    ┌────▼────┐
                    │Aggregate│  (dedupe, sort, limit)
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Publish │  (post to GitHub)
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Notify  │  (Slack)
                    └─────────┘
```

### 3. GraphState (`src/agents/state.py`)

**Nhiệm vụ:** Định nghĩa data schema cho workflow.

```python
class GraphState(TypedDict):
    context: PRContext           # PR metadata
    files: list[FileChange]      # Files changed
    comments: list[ReviewComment] # Agent outputs (merged)
    final_comments: list[ReviewComment]  # After aggregation
    summary: str                 # Review summary
    review_id: int | None        # GitHub review ID
    errors: list[str]            # Any errors
```

**Key insight:** `comments` dùng `operator.add` để merge output từ 3 agents.

### 4. AI Agents (`src/agents/nodes/`)

Mỗi agent có cùng pattern:

```python
async def run(state: GraphState) -> dict:
    llm = get_llm()
    comments = []

    for file in state["files"]:
        # 1. Format prompt với file diff
        prompt = PROMPT.format(filename=..., diff=...)

        # 2. Call LLM
        response = await llm.ainvoke(prompt)

        # 3. Parse JSON findings
        findings = _parse_findings(response.content)

        # 4. Filter by confidence > 0.7
        for f in findings:
            if f["confidence"] >= 0.7:
                comments.append(ReviewComment(...))

    return {"comments": comments}
```

**Agent Focus:**
| Agent | Tìm kiếm |
|-------|----------|
| Security | SQL injection, XSS, hardcoded secrets, SSRF |
| Style | Naming, formatting, dead code, missing docs |
| Logic | Null refs, off-by-one, missing error handling |

### 5. GitHub Service (`src/app/services/github.py`)

**Nhiệm vụ:** Authenticate via GitHub App, call GitHub API.

```python
# 1. Tạo JWT từ App Private Key
jwt = jwt.encode({"iss": APP_ID, ...}, PRIVATE_KEY, "RS256")

# 2. Exchange JWT → Installation Token
POST /app/installations/{id}/access_tokens

# 3. Dùng Installation Token để call API
GET /repos/{owner}/{repo}/pulls/{pr}/files
POST /repos/{owner}/{repo}/pulls/{pr}/reviews
```

### 6. Celery Worker (`src/workers/`)

**Nhiệm vụ:** Background processing với retry logic.

```python
@celery_app.task(bind=True, max_retries=3)
def review_pr(self, owner, repo, pr_number, installation_id):
    try:
        result = asyncio.run(graph.ainvoke(initial_state))
    except Exception as e:
        raise self.retry(exc=e, countdown=60)  # Retry sau 60s
```

---

## 🔐 Security Model

### GitHub App Authentication

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Private   │   JWT   │   GitHub    │  Token  │   GitHub    │
│     Key     │ ──────▶ │    API      │ ──────▶ │    API      │
│  (RS256)    │         │  /access_   │         │  /repos/... │
└─────────────┘         │   tokens    │         └─────────────┘
                        └─────────────┘

JWT lifetime: 10 min
Token lifetime: 1 hour
```

### Webhook Signature

```python
# GitHub sends: X-Hub-Signature-256: sha256=abc123...
# We verify:
expected = hmac.new(WEBHOOK_SECRET, body, sha256).hexdigest()
hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 📊 Data Flow Example

**Input (PR với 2 files):**

```json
{
  "action": "opened",
  "pull_request": { "number": 42 },
  "repository": { "name": "my-app", "owner": { "login": "org" } }
}
```

**After Context Extractor:**

```python
files = [
    FileChange(filename="api.py", patch="+ query = f'SELECT * FROM {user_input}'"),
    FileChange(filename="utils.py", patch="+ x = data.value"),
]
```

**After Security Agent:**

```python
comments = [
    ReviewComment(
        file="api.py", line=15,
        severity="critical", category="security",
        message="SQL injection via f-string",
        suggestion="Use parameterized queries"
    )
]
```

**After Aggregator:**

```markdown
## 🤖 AI Code Review

| Severity    | Count |
| ----------- | ----- |
| 🔴 Critical | 1     |
| 🟡 Warning  | 0     |

**Total: 1 comments**
```

**On GitHub:**

> 🔴 **CRITICAL** (security)
>
> SQL injection via f-string
>
> **Suggestion:** Use parameterized queries

---

## ⚙️ Configuration

| Env Var                 | Mô tả                              |
| ----------------------- | ---------------------------------- |
| `GITHUB_APP_ID`         | ID của GitHub App                  |
| `GITHUB_PRIVATE_KEY`    | RSA private key (PEM format)       |
| `GITHUB_WEBHOOK_SECRET` | Secret để verify webhook signature |
| `OPENAI_API_KEY`        | API key cho GPT-4                  |
| `REDIS_URL`             | URL của Redis (Celery broker)      |
| `SLACK_BOT_TOKEN`       | Optional: Slack notifications      |

---

## 🧪 Testing Locally

```bash
# 1. Start ngrok
ngrok http 8000

# 2. Configure GitHub App webhook URL
# https://abc123.ngrok.io/api/v1/webhooks/github

# 3. Start services
make dev     # FastAPI
make worker  # Celery

# 4. Create a test PR
# Watch logs for processing
```

---

## 📈 Scalability Notes

- **Horizontal scaling:** Thêm Celery workers
- **Rate limiting:** GitHub API = 5000 req/hour per installation
- **Token caching:** Installation tokens cached ~1 hour
- **Parallel agents:** 3 agents chạy đồng thời via LangGraph
