# 🏗️ Architecture - Auto-Fix Feature

## 📊 CodeRabbit vs MVP Hiện Tại

### MVP Hiện Tại (1 Luồng Duy Nhất)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────┘

  GitHub PR Event
       │
       ▼
  ┌─────────────┐
  │  Webhook    │ ──▶ Validate signature
  │  Handler    │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Celery Task │ ──▶ review_pr.delay()
  │  Queue      │
  └──────┬──────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    LANGGRAPH WORKFLOW                        │
  │                                                              │
  │   extract ──┬──▶ security ──┐                               │
  │             ├──▶ style    ──┼──▶ aggregate ──▶ publish      │
  │             └──▶ logic    ──┘               ──▶ notify      │
  │                                                              │
  └─────────────────────────────────────────────────────────────┘
         │
         ▼
  GitHub PR Comments
```

**Limitations:**

- Chỉ xử lý `pull_request` event
- Không hỗ trợ interactive commands
- Không có on-demand fix generation

---

### CodeRabbit Architecture (2 Luồng Tách Biệt)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CODERABBIT ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────┘

                    GitHub Events
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
  ┌──────────────┐                ┌──────────────┐
  │ pull_request │                │ issue_comment│
  │    event     │                │    event     │
  └──────┬───────┘                └──────┬───────┘
         │                               │
         ▼                               ▼
  ┌──────────────┐                ┌──────────────┐
  │  FLOW 1:     │                │  FLOW 2:     │
  │  Auto Review │                │  On-Demand   │
  │  (Passive)   │                │  (Active)    │
  └──────┬───────┘                └──────┬───────┘
         │                               │
         ▼                               ▼
  ┌──────────────┐                ┌──────────────┐
  │ Analyze code │                │ Parse command│
  │ Post comments│                │ Execute task │
  │ (NO fixes)   │                │ Post result  │
  └──────────────┘                └──────────────┘
```

---

## 🎯 Proposed Architecture Cho Dự Án

````
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSED ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────┘

                         GitHub Webhook
                              │
                              ▼
                    ┌─────────────────┐
                    │ Webhook Handler │
                    │ (webhooks.py)   │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ Event Type:     │           │ Event Type:     │
    │ pull_request    │           │ issue_comment   │
    │                 │           │                 │
    │ Actions:        │           │ Check for:      │
    │ opened          │           │ @reviewer       │
    │ synchronize     │           │ commands        │
    │ reopened        │           │                 │
    └────────┬────────┘           └────────┬────────┘
             │                             │
             ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ review_pr       │           │ handle_command  │
    │ Celery Task     │           │ Celery Task     │
    └────────┬────────┘           └────────┬────────┘
             │                             │
             ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   LANGGRAPH     │           │  COMMAND        │
    │   WORKFLOW      │           │  HANDLER        │
    │                 │           │                 │
    │ ┌─────────────┐ │           │ Commands:       │
    │ │ Security    │ │           │ • fix           │
    │ │ Style       │ │           │ • generate tests│
    │ │ Logic       │ │           │ • explain       │
    │ │ Aggregate   │ │           │ • re-review     │
    │ │ Publish     │ │           │                 │
    │ └─────────────┘ │           │ Uses LLM to     │
    │                 │           │ generate code   │
    └────────┬────────┘           └────────┬────────┘
             │                             │
             ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ PR Review       │           │ PR Comment      │
    │ Comments        │           │ Reply with      │
    │                 │           │ ```suggestion   │
    │ "Issue found"   │           │ <fixed code>    │
    │ "@reviewer fix" │           │ ```             │
    └─────────────────┘           └─────────────────┘
````

---

## 📁 File Structure Changes

```
src/
├── app/
│   ├── api/v1/
│   │   └── webhooks.py        # UPDATE: Add issue_comment handling
│   └── services/
│       └── github.py          # UPDATE: Add reply_to_comment method
│
├── agents/
│   ├── nodes/
│   │   └── github_publisher.py # UPDATE: Add CTA in comments
│   └── graph.py               # NO CHANGE (review flow unchanged)
│
├── chat/                      # NEW DIRECTORY
│   ├── __init__.py
│   ├── parser.py              # Parse @reviewer commands
│   ├── handler.py             # Route to appropriate handler
│   └── commands/
│       ├── __init__.py
│       ├── fix.py             # Generate fix for issue
│       ├── test.py            # Generate unit tests
│       └── explain.py         # Explain an issue
│
└── workers/
    └── tasks.py               # UPDATE: Add handle_command task
```

---

## 🔄 Data Flow Comparison

### Current: Review Only

```
PR Created
    │
    └──▶ review_pr task
              │
              └──▶ LangGraph (Security → Style → Logic → Aggregate → Publish)
                        │
                        └──▶ GitHub Comments
                                 │
                                 └──▶ "SQL Injection found. Use parameterized queries."
                                          │
                                          └──▶ Developer manually fixes 😓
```

### Proposed: Review + On-Demand Fix

````
PR Created
    │
    └──▶ review_pr task
              │
              └──▶ LangGraph workflow
                        │
                        └──▶ GitHub Comment:
                                 │
                                 │ "🔴 SQL Injection found.
                                 │  Reply @reviewer fix this"
                                 │
                                 └──▶ Developer replies "@reviewer fix this"
                                          │
                                          └──▶ issue_comment webhook
                                                    │
                                                    └──▶ handle_command task
                                                              │
                                                              └──▶ Generate fix
                                                                        │
                                                                        └──▶ Reply:
                                                                             ```suggestion
                                                                             cursor.execute(
                                                                                "SELECT * FROM users WHERE id = ?",
                                                                                (user_id,)
                                                                             )
                                                                             ```
                                                                                  │
                                                                                  └──▶ Developer clicks
                                                                                       "Commit suggestion" 🎉
````

---

## 🎯 Key Decisions

| Decision                     | Rationale                                 |
| ---------------------------- | ----------------------------------------- |
| **Tách 2 flows**             | Giống CodeRabbit, giảm complexity và cost |
| **On-demand fix**            | User control, chỉ generate khi cần        |
| **Reply to comment**         | Context-aware, biết issue nào cần fix     |
| **GitHub suggestion syntax** | Native commit experience                  |
| **New chat/ directory**      | Clean separation of concerns              |
