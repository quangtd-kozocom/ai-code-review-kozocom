# 🔌 MCP Server Integration

> Tích hợp Model Context Protocol để bổ sung external context vào reviews

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Cao  
**Tham khảo:** CodeRabbit MCP, Anthropic Model Context Protocol

---

## 📋 Mô Tả

Sử dụng MCP (Model Context Protocol) để AI reviewer có thể:

1. Truy cập documentation nội bộ
2. Đọc Jira/Linear tickets liên quan
3. Hiểu business context từ wikis
4. Reference coding standards của team

---

## 🎯 Mục Tiêu

- **Primary:** Context-aware reviews hiểu business logic
- **Secondary:** Enforce team-specific coding standards
- **Tertiary:** Liên kết reviews với project management tools

---

## 💡 Use Cases

### 1. Documentation Context

```
AI reads: "According to API docs, this endpoint requires auth"
Review: "Missing authentication middleware as per API specification"
```

### 2. Ticket Compliance

```
AI reads: "JIRA-123 requires input validation"
Review: "This PR addresses JIRA-123 but missing email validation"
```

### 3. Coding Standards

```
AI reads: "Team standard: All API errors use ErrorResponse class"
Review: "Use ErrorResponse instead of raw dict for consistency"
```

---

## 🛠️ Technical Implementation

### MCP Server Setup

```python
# src/mcp/server.py

from mcp import MCPServer
from mcp.resources import Resource

class ReviewerMCPServer(MCPServer):
    """MCP server providing context to AI reviewer."""

    def __init__(self):
        super().__init__()
        self.register_resource("docs", DocsResource())
        self.register_resource("tickets", TicketResource())
        self.register_resource("standards", StandardsResource())
```

### Context Integration

```python
# src/agents/nodes/context_enricher.py

async def run(state: GraphState) -> dict:
    """Enrich review with external context via MCP."""
    mcp = MCPClient()

    # Fetch relevant docs
    docs = await mcp.fetch("docs", query=state["context"].repo)

    # Get linked tickets
    tickets = await mcp.fetch("tickets", pr=state["context"].pr_number)

    return {
        "external_context": {
            "docs": docs,
            "tickets": tickets,
        }
    }
```

---

## ✅ Acceptance Criteria

1. [ ] Connect to MCP servers for external context
2. [ ] Incorporate docs into security/logic reviews
3. [ ] Check ticket compliance
4. [ ] Support custom team standards

---

## 📊 Metrics

| Metric                   | Target |
| ------------------------ | ------ |
| Context-enriched reviews | > 50%  |
| Ticket compliance checks | > 90%  |
