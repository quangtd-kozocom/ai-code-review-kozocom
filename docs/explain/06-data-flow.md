# 🌊 Luồng Dữ Liệu từ Đầu đến Cuối

## 1. End-to-End Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Complete Data Flow                                    │
│                                                                              │
│   GITHUB WEBHOOK                                                             │
│   ┌────────────────────┐                                                     │
│   │ PR Event:          │                                                     │
│   │   action: opened   │                                                     │
│   │   pr_number: 123   │                                                     │
│   │   owner: org       │                                                     │
│   │   repo: myrepo     │                                                     │
│   └─────────┬──────────┘                                                     │
│             │                                                                │
│             ▼                                                                │
│   ┌────────────────────┐                                                     │
│   │ Celery Task:       │  (Background processing)                            │
│   │   process_pr_review│                                                     │
│   └─────────┬──────────┘                                                     │
│             │                                                                │
│             ▼                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                     LangGraph Workflow                              │    │
│   │                                                                     │    │
│   │  Initial State:                                                     │    │
│   │  ┌────────────────────────────────────────────────────────────┐    │    │
│   │  │ context: PRContext(owner, repo, pr_number, title, author,  │    │    │
│   │  │                    installation_id)                         │    │    │
│   │  │ files: []                                                   │    │    │
│   │  │ comments: []                                                │    │    │
│   │  └────────────────────────────────────────────────────────────┘    │    │
│   │                           │                                         │    │
│   │                           ▼                                         │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ ACKNOWLEDGE: Post "AI Review Started" comment               │   │    │
│   │  │              → acknowledge_comment_id: 12345                │   │    │
│   │  └──────────────────────────┬──────────────────────────────────┘   │    │
│   │                             │                                       │    │
│   │                             ▼                                       │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ EXTRACT: Fetch PR files from GitHub API                     │   │    │
│   │  │          Filter: ignore *.lock, *.min.js, images...         │   │    │
│   │  │          Detect: language from extension                    │   │    │
│   │  │          → files: [FileChange(...), FileChange(...)]        │   │    │
│   │  └──────────────────────────┬──────────────────────────────────┘   │    │
│   │                             │                                       │    │
│   │              ┌──────────────┼──────────────┐                       │    │
│   │              │              │              │                        │    │
│   │              ▼              ▼              ▼                        │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│   │  │   SECURITY   │  │    STYLE     │  │    LOGIC     │  PARALLEL   │    │
│   │  │   LLM Call   │  │   LLM Call   │  │   LLM Call   │              │    │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │    │
│   │         │                 │                 │                       │    │
│   │         └─────────────────┼─────────────────┘                       │    │
│   │                           │                                         │    │
│   │                           ▼                                         │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ comments: [merged from 3 agents via operator.add]           │   │    │
│   │  └──────────────────────────┬──────────────────────────────────┘   │    │
│   │                             │                                       │    │
│   │                             ▼                                       │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ AGGREGATE: Dedupe → Sort → Limit                            │   │    │
│   │  │            → final_comments: [top comments]                 │   │    │
│   │  │            → summary: "## 🤖 AI Review..."                  │   │    │
│   │  └──────────────────────────┬──────────────────────────────────┘   │    │
│   │                             │                                       │    │
│   │                             ▼                                       │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ PUBLISH: Create GitHub PR Review                            │   │    │
│   │  │          Event: REQUEST_CHANGES or COMMENT                  │   │    │
│   │  │          → review_id: 98765                                 │   │    │
│   │  └──────────────────────────┬──────────────────────────────────┘   │    │
│   │                             │                                       │    │
│   │                             ▼                                       │    │
│   │  ┌─────────────────────────────────────────────────────────────┐   │    │
│   │  │ NOTIFY: Send Slack notification (if findings)               │   │    │
│   │  └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│   Final State:                                                               │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │ context: PRContext(...)                                            │    │
│   │ files: [FileChange, ...]                                           │    │
│   │ comments: [all ReviewComments from agents]                         │    │
│   │ final_comments: [filtered, sorted, limited]                        │    │
│   │ summary: "## 🤖 AI Code Review\n..."                               │    │
│   │ acknowledge_comment_id: 12345                                      │    │
│   │ review_id: 98765                                                   │    │
│   │ errors: []                                                         │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. Data Transformation Summary

| Stage       | Input            | Output                    |
| ----------- | ---------------- | ------------------------- |
| Webhook     | HTTP Request     | PRContext                 |
| Acknowledge | PRContext        | comment_id                |
| Extract     | PRContext        | files[]                   |
| 3 Agents    | files[]          | comments[]                |
| Aggregate   | comments[]       | final_comments[], summary |
| Publish     | final_comments[] | review_id                 |
| Notify      | summary          | (side effect)             |

## 3. Key Design Decisions

1. **Parallel AI calls** → Giảm ~3x latency
2. **Auto-merge với operator.add** → Đơn giản hóa fan-in
3. **Confidence filtering** → Giảm false positives
4. **Limit per file** → Tránh spam comments
5. **Non-blocking errors** → Workflow tiếp tục dù có lỗi
