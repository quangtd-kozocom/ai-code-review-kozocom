# 🏗️ Tổng quan kiến trúc Agents

## 1. Mô hình tổng quan

Hệ thống Agents sử dụng **LangGraph** để xây dựng một workflow có cấu trúc DAG (Directed Acyclic Graph) với pattern **fan-out/fan-in** để xử lý song song các tác vụ AI.

```
                                    ┌──────────────────┐
                                    │   Webhook        │
                                    │   (PR Event)     │
                                    └────────┬─────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LangGraph Workflow                                │
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐                                     │
│   │ Acknowledge │ ───▶ │  Extract    │                                     │
│   │ (Notify PR) │      │  Context    │                                     │
│   └─────────────┘      └──────┬──────┘                                     │
│                               │                                             │
│                   ┌───────────┼───────────┐    ◀─── Fan-out (Parallel)     │
│                   ▼           ▼           ▼                                 │
│            ┌──────────┐ ┌──────────┐ ┌──────────┐                          │
│            │ Security │ │  Style   │ │  Logic   │    ◀─── 3 AI Agents      │
│            │  Agent   │ │  Agent   │ │  Agent   │                          │
│            └────┬─────┘ └────┬─────┘ └────┬─────┘                          │
│                 │            │            │                                 │
│                 └────────────┼────────────┘    ◀─── Fan-in (Merge)         │
│                              ▼                                              │
│                       ┌──────────────┐                                     │
│                       │  Aggregator  │                                     │
│                       │  (Dedupe &   │                                     │
│                       │   Limit)     │                                     │
│                       └──────┬───────┘                                     │
│                              │                                              │
│                              ▼                                              │
│                       ┌──────────────┐                                     │
│                       │   GitHub     │                                     │
│                       │  Publisher   │                                     │
│                       └──────┬───────┘                                     │
│                              │                                              │
│                              ▼                                              │
│                       ┌──────────────┐                                     │
│                       │    Slack     │                                     │
│                       │   Reporter   │                                     │
│                       └──────────────┘                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. Các thành phần chính

### 2.1. State Management (`state.py`)

Định nghĩa cấu trúc dữ liệu được truyền qua các node trong graph:

- **PRContext**: Thông tin về Pull Request
- **FileChange**: Thông tin về file thay đổi
- **ReviewComment**: Comment từ các AI agents
- **GraphState**: State tổng thể của workflow

### 2.2. Graph Definition (`graph.py`)

Sử dụng LangGraph `StateGraph` để:

- Định nghĩa các nodes (các bước xử lý)
- Định nghĩa edges (kết nối giữa các bước)
- Set entry point và end point
- Compile thành executable graph

### 2.3. Nodes (`nodes/`)

8 nodes thực hiện các nhiệm vụ cụ thể:

| Node                | Chức năng                         |
| ------------------- | --------------------------------- |
| `acknowledger`      | Gửi comment thông báo đang review |
| `context_extractor` | Lấy danh sách files từ GitHub PR  |
| `security_agent`    | Phân tích lỗ hổng bảo mật         |
| `style_agent`       | Phân tích code style              |
| `logic_agent`       | Phân tích logic và bugs           |
| `aggregator`        | Gộp, dedupe, giới hạn comments    |
| `github_publisher`  | Đăng review lên GitHub            |
| `slack_reporter`    | Gửi thông báo Slack               |

### 2.4. Prompts (`prompts/`)

Template prompts cho LLM, được thiết kế để:

- Nhận context (filename, language, diff)
- Trả về JSON với findings
- Có confidence score và severity levels

## 3. Đặc điểm kỹ thuật

### 3.1. Parallel Processing

- 3 AI agents chạy **song song** (fan-out)
- Kết quả được **merge** vào `comments` list (fan-in)
- Sử dụng `operator.add` để auto-merge lists

### 3.2. Concurrency Control

- Mỗi agent có `Semaphore` giới hạn concurrent LLM calls
- `MAX_CONCURRENT_CALLS = 5` per agent
- Tránh rate limiting từ LLM provider

### 3.3. Error Handling

- Mỗi node có try/catch riêng
- Lỗi không làm fail toàn bộ workflow
- Errors được log và lưu vào state

### 3.4. Singleton Pattern

```python
# graph.py
graph = create_graph()  # Compiled once, reused
```

## 4. Luồng dữ liệu chính

```
PRContext  →  Files[]  →  Comments[]  →  FinalComments[]  →  Review + Notification
   │             │            │                │                     │
   │             │            │                │                     │
   ▼             ▼            ▼                ▼                     ▼
Webhook     Extract      3 Agents       Aggregator          Publisher + Slack
```

---

**Tiếp theo:** [02-state-management.md](./02-state-management.md) - Chi tiết về quản lý State
