# 🧩 Chi tiết từng Node trong Workflow

## Tổng quan 8 Nodes

| #   | Node        | File                   | Vai trò                  |
| --- | ----------- | ---------------------- | ------------------------ |
| 1   | acknowledge | `acknowledger.py`      | Gửi comment "đang xử lý" |
| 2   | extract     | `context_extractor.py` | Lấy files từ PR          |
| 3   | security    | `security_agent.py`    | Phân tích security       |
| 4   | style       | `style_agent.py`       | Phân tích style          |
| 5   | logic       | `logic_agent.py`       | Phân tích logic/bugs     |
| 6   | aggregate   | `aggregator.py`        | Tổng hợp comments        |
| 7   | publish     | `github_publisher.py`  | Post review lên GitHub   |
| 8   | notify      | `slack_reporter.py`    | Gửi Slack notification   |

---

## 1. Acknowledger Node 📢

**Purpose:** Gửi comment ngay lập tức thông báo AI đang review.

**Message:**

```
🤖 **AI Code Review Started**
I'm analyzing your pull request...
```

**Output:** `{"acknowledge_comment_id": 123456789}`

**Error handling:** Non-blocking (không fail workflow)

---

## 2. Context Extractor Node 📁

**Purpose:** Lấy files từ PR, filter bỏ files không cần review.

**Ignore patterns:** `*.lock`, `*.min.js`, `node_modules/*`, `*.svg`, `*.png`...

**Language detection:** `.py → python`, `.ts → typescript`...

**Output:** `{"files": [FileChange, ...]}`

---

## 3-5. AI Agents (Security, Style, Logic) 🤖

**Chung cấu trúc:**

```python
MAX_CONCURRENT_CALLS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

async def process_file(file):
    prompt = PROMPT.format(filename, language, diff)
    async with semaphore:
        response = await llm.ainvoke(prompt)
    findings = _parse_findings(response.content)
    # Filter confidence >= 0.7
    return [ReviewComment(...) for finding in findings]

tasks = [process_file(f) for f in files]
results = await asyncio.gather(*tasks)
```

**Output:** `{"comments": [ReviewComment(agent="xxx"), ...]}`

---

## 6. Aggregator Node 🔗

**Purpose:** Dedupe, sort, limit comments.

**Steps:**

1. **Dedupe** by `(file, line, category)`
2. **Sort** by severity → confidence
3. **Limit** 10 comments per file
4. **Generate summary** markdown table

**Output:** `{"final_comments": [...], "summary": "## 🤖 AI Review..."}`

---

## 7. GitHub Publisher Node 📤

**Purpose:** Post review lên GitHub PR.

**Actions:**

- Format comments với emoji (🔴🟡🔵💡)
- Decide event: `REQUEST_CHANGES` nếu có critical, else `COMMENT`
- Call GitHub API

**Output:** `{"review_id": 987654321}`

---

## 8. Slack Reporter Node 💬

**Purpose:** Gửi Slack notification.

**Conditions:** Chỉ gửi nếu có findings

**Output:** `{}` (side effect only)

---

**Tiếp theo:** [05-prompts-design.md](./05-prompts-design.md)
