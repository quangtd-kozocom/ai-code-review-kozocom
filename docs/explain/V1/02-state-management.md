# 📦 Quản lý State với TypedDict và Pydantic

## 1. Tổng quan

State management trong hệ thống sử dụng kết hợp:

- **Pydantic BaseModel**: Cho data validation và serialization
- **TypedDict**: Cho LangGraph state definition
- **Annotated + operator.add**: Cho auto-merging parallel results

## 2. Data Models (Pydantic)

### 2.1. FileChange - Thông tin file thay đổi

```python
class FileChange(BaseModel):
    """A file changed in the PR."""

    filename: str                                      # Tên file
    status: Literal["added", "modified", "removed", "renamed"]  # Trạng thái
    additions: int                                     # Số dòng thêm
    deletions: int                                     # Số dòng xóa
    patch: str                                         # Git diff content
    language: str | None = None                        # Ngôn ngữ (auto-detected)
```

**Ví dụ:**

```json
{
  "filename": "src/api/users.py",
  "status": "modified",
  "additions": 15,
  "deletions": 3,
  "patch": "@@ -10,3 +10,15 @@\n+def create_user():\n+    ...",
  "language": "python"
}
```

### 2.2. ReviewComment - Comment từ AI Agent

```python
class ReviewComment(BaseModel):
    """A review comment from an agent."""

    file: str                                          # File đang review
    line: int                                          # Số dòng
    severity: Literal["critical", "warning", "info", "suggestion"]  # Mức độ
    category: str                                      # security | style | logic
    message: str                                       # Nội dung comment
    suggestion: str | None = None                      # Gợi ý fix (optional)
    confidence: float = Field(ge=0.0, le=1.0)          # Độ tin cậy 0-1
    agent: str                                         # Agent nào tạo
```

**Ví dụ:**

```json
{
  "file": "src/api/auth.py",
  "line": 42,
  "severity": "critical",
  "category": "security",
  "message": "SQL injection via string concatenation",
  "suggestion": "Use parameterized queries instead",
  "confidence": 0.95,
  "agent": "security"
}
```

### 2.3. PRContext - Thông tin Pull Request

```python
class PRContext(BaseModel):
    """Context about the PR being reviewed."""

    owner: str               # GitHub organization/user
    repo: str                # Repository name
    pr_number: int           # PR number
    title: str               # PR title
    author: str              # PR author
    installation_id: int     # GitHub App installation ID
```

## 3. GraphState (TypedDict)

```python
class GraphState(TypedDict):
    """State passed through the LangGraph workflow."""

    # Input
    context: PRContext                                  # Thông tin PR

    # Extracted
    files: list[FileChange]                             # Danh sách files

    # Agent outputs (merged via operator.add)
    comments: Annotated[list[ReviewComment], operator.add]  # ⭐ Auto-merge

    # Aggregated
    final_comments: list[ReviewComment]                 # Comments sau khi filter
    summary: str                                        # Markdown summary

    # Output
    acknowledge_comment_id: int | None                  # Comment ID đầu tiên
    review_id: int | None                               # GitHub Review ID
    errors: list[str]                                   # Lỗi nếu có
```

## 4. Magic: Annotated + operator.add

### 4.1. Vấn đề: Fan-in từ 3 agents

```
Security Agent  ─┐
                 ├──▶  Cần merge thành 1 list comments
Style Agent    ─┤
                 │
Logic Agent    ─┘
```

### 4.2. Giải pháp: Auto-merge với operator.add

```python
# Khai báo
comments: Annotated[list[ReviewComment], operator.add]

# Khi Security agent trả về:
{"comments": [comment1, comment2]}

# Khi Style agent trả về:
{"comments": [comment3]}

# Khi Logic agent trả về:
{"comments": [comment4, comment5]}

# LangGraph tự động merge:
state["comments"] = [comment1, comment2, comment3, comment4, comment5]
```

### 4.3. Cơ chế hoạt động

```
┌────────────────────────────────────────────────────────────────┐
│                    LangGraph State Update                      │
│                                                                │
│   1. Node returns: {"comments": [new_comments]}                │
│   2. LangGraph sees: comments has Annotated[..., operator.add] │
│   3. Instead of: state["comments"] = new_comments              │
│      It does:    state["comments"] = old + new_comments        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## 5. State Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Initial State                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ context: PRContext(owner, repo, pr_number, ...)            │ │
│ │ files: []                                                   │ │
│ │ comments: []                                                │ │
│ │ final_comments: []                                          │ │
│ │ summary: ""                                                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ After Acknowledger                                              │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ + acknowledge_comment_id: 123456789                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ After Context Extractor                                         │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ + files: [FileChange(...), FileChange(...), ...]            │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ After 3 AI Agents (Parallel)                                    │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ + comments: [                                               │ │
│ │     ReviewComment(agent="security", ...),                   │ │
│ │     ReviewComment(agent="security", ...),                   │ │
│ │     ReviewComment(agent="style", ...),                      │ │
│ │     ReviewComment(agent="logic", ...),                      │ │
│ │   ]                                                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ After Aggregator                                                │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ + final_comments: [filtered, deduped, limited comments]     │ │
│ │ + summary: "## 🤖 AI Code Review\n| Severity | Count |..."  │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Final State                                                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ + review_id: 987654321                                      │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Tại sao dùng Pydantic + TypedDict?

| Aspect            | Pydantic BaseModel | TypedDict         |
| ----------------- | ------------------ | ----------------- |
| **Validation**    | ✅ Auto-validate   | ❌ Không validate |
| **Serialization** | ✅ .model_dump()   | ❌ Thủ công       |
| **Type hints**    | ✅ Rich            | ✅ Basic          |
| **LangGraph**     | ❌ Không native    | ✅ Native support |

**Kết hợp:**

- `Pydantic` cho data models (FileChange, ReviewComment, PRContext)
- `TypedDict` cho GraphState (LangGraph requirement)
- Pydantic models được lưu trong TypedDict fields

---

**Tiếp theo:** [03-graph-workflow.md](./03-graph-workflow.md) - Chi tiết về LangGraph workflow
