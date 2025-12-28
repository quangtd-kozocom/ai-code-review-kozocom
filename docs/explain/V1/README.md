# 📚 Giải thích hệ thống Agents

> Tài liệu giải thích chi tiết cách hoạt động của thư mục `src/agents` - hệ thống AI Code Review dựa trên LangGraph.

## 📁 Cấu trúc thư mục

```
src/agents/
├── __init__.py          # Export các class/function chính
├── state.py             # Định nghĩa State và Data Models
├── graph.py             # Định nghĩa workflow graph (LangGraph)
├── nodes/               # Các node xử lý trong workflow
│   ├── acknowledger.py      # Gửi thông báo "đang xử lý"
│   ├── context_extractor.py # Trích xuất file từ PR
│   ├── security_agent.py    # Phân tích bảo mật
│   ├── style_agent.py       # Phân tích code style
│   ├── logic_agent.py       # Phân tích logic/bugs
│   ├── aggregator.py        # Tổng hợp comments
│   ├── github_publisher.py  # Đăng review lên GitHub
│   └── slack_reporter.py    # Gửi thông báo Slack
└── prompts/             # Prompt templates cho LLM
    ├── security.py
    ├── style.py
    └── logic.py
```

## 🔗 Tài liệu chi tiết

| File                                                         | Mô tả                                       |
| ------------------------------------------------------------ | ------------------------------------------- |
| [01-architecture-overview.md](./01-architecture-overview.md) | Tổng quan kiến trúc và luồng hoạt động      |
| [02-state-management.md](./02-state-management.md)           | Quản lý state với TypedDict và Pydantic     |
| [03-graph-workflow.md](./03-graph-workflow.md)               | LangGraph workflow - fan-out/fan-in pattern |
| [04-nodes-detail.md](./04-nodes-detail.md)                   | Chi tiết từng node trong workflow           |
| [05-prompts-design.md](./05-prompts-design.md)               | Thiết kế prompt cho các AI agents           |
| [06-data-flow.md](./06-data-flow.md)                         | Luồng dữ liệu từ đầu đến cuối               |
