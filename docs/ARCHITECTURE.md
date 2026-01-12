# AI Code Review - LangGraph Architecture

## Tổng quan

Hệ thống AI Code Review sử dụng **LangGraph** để xây dựng một workflow linh hoạt cho việc review Pull Request tự động. Workflow được thiết kế theo mô hình **file-by-file processing** với khả năng **loop** và **conditional routing**.

## Kiến trúc Workflow

```
┌─────────────────┐
│  Extract Diff   │ ← Entry Point
│    (Start)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Clone Repo    │ ← Shallow clone (depth=1, blob filter)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Get Next File  │◄────────────────────────────────┐
└────────┬────────┘                                 │
         │                                          │
         ▼                                          │
┌─────────────────┐                                 │
│  Analyze File   │ ← LLM phát hiện breaking changes│
│     (LLM)       │                                 │
└────────┬────────┘                                 │
         │                                          │
         ▼                                          │
┌─────────────────┐                                 │
│   Plan Search   │ ← LLM quyết định search queries │
│     (LLM)       │◄──────────┐                     │
└────────┬────────┘           │                     │
         │                    │ More Search         │
         ▼                    │ Needed              │
┌─────────────────┐           │                     │
│ Execute Search  │           │                     │
│   (Ripgrep)     │           │                     │
└────────┬────────┘           │                     │
         │                    │                     │
         ▼                    │                     │
┌─────────────────┐           │                     │
│  Verify Impact  │───────────┘                     │
│     (LLM)       │                                 │
└────────┬────────┘                                 │
         │                                          │
         ▼                                          │
┌─────────────────┐                                 │
│Generate Review  │                                 │
│     (LLM)       │                                 │
└────────┬────────┘                                 │
         │                                          │
         ▼                                          │
┌─────────────────┐                                 │
│ Publish GitHub  │ ← Immediate publishing          │
└────────┬────────┘                                 │
         │                                          │
         └──────────────────────────────────────────┘
                              │
                              ▼ (All files done)
                    ┌─────────────────┐
                    │ Finalize Review │
                    │  (DB + Slack)   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Cleanup     │
                    └────────┬────────┘
                             │
                             ▼
                           [END]
```

## Các Node chính

### 1. Extract Diff (`extract_diff.py`)
- Lấy danh sách files thay đổi từ GitHub PR
- Filter chỉ giữ code files (`.py`, `.php`, `.js`, `.ts`, etc.)
- Áp dụng include/exclude patterns từ config

### 2. Clone Repo (`clone_repo.py`)
- **Shallow Clone**: `--depth 1` - chỉ clone 1 commit
- **Blob Filter**: `--filter=blob:limit=1m` - bỏ qua files > 1MB
- **Single Branch**: Chỉ clone branch của PR
- Tạo temp directory để search local

### 3. Analyze File (`analyze_file.py`)
- **Input**: File diff (old content, new content, patch)
- **LLM Task**: Phát hiện breaking changes
- **Output**: Danh sách `DetectedChange` với:
  - Entity type (function, method, constant, class...)
  - Change type (signature_changed, deleted, renamed...)
  - Line number trong file mới

### 4. Plan Search (`plan_search.py`)
- **Input**: `DetectedChange` cần tìm callers
- **LLM Task**: Quyết định search queries
- **Output**: `SearchPlan` với:
  - Queries (text patterns)
  - Include patterns (`*.php`, `*.js`)
  - Exclude patterns (`*test*`, `vendor/*`)

### 5. Execute Search (`execute_search.py`)
- **Tool**: Ripgrep (rg)
- **Tốc độ**: Milliseconds
- **Không rate limit**: Search local, không gọi GitHub API
- **Output**: `SearchResult` với file path, line, context

### 6. Verify Impact (`verify_impact.py`)
- **Input**: Search results + Change info
- **LLM Task**: Xác minh callers thực sự bị ảnh hưởng
- **Output**: 
  - `AffectedCaller` list
  - `need_more_search` flag
  - `additional_queries` nếu cần search thêm

### 7. Generate Review (`generate_file_review.py`)
- **Input**: Breaking changes + Affected callers
- **LLM Task**: Tạo review comment có format chuẩn
- **Output**: `ReviewComment` với severity, message, recommendation

### 8. Publish GitHub (`publish_github.py`)
- Post inline review comment
- Fallback to issue comment nếu line không trong diff
- **Immediate Publishing**: Post ngay sau mỗi file

### 9. Finalize Review (`finalize_review.py`)
- Lưu kết quả vào Database
- Gửi summary qua Slack
- Chạy parallel (DB + Slack)

## State Management

```python
class ReviewState(TypedDict):
    # Input
    pr_context: PRContext
    config: RepoConfig | None
    
    # File loop
    pending_files: list[FileDiff]
    current_file: FileDiff | None
    
    # Per-file analysis
    file_changes: list[DetectedChange]
    current_change: DetectedChange | None
    
    # Search loop
    search_plan: SearchPlan | None
    search_results: list[SearchResult]
    need_more_search: bool
    search_iteration: int
    
    # Results (accumulated)
    all_breaking_changes: list[BreakingChange]  # operator.add
    all_comments: list[ReviewComment]           # operator.add
    published_comments: list[ReviewComment]     # operator.add
```

## Routing Logic

### Conditional Edges

1. **After Extract Diff**:
   - `skip_review=True` → Cleanup → END
   - Else → Clone Repo

2. **After Get File**:
   - `current_file=None` → Finalize Review
   - Else → Analyze File

3. **After Analyze**:
   - No breaking changes → Get Next File
   - Has changes → Plan Search

4. **After Verify Impact** (quan trọng nhất):
   - `need_more_search=True` → Plan Search (loop)
   - More changes in file → Next Change → Plan Search
   - All done → Generate Review

## Điểm đột phá kỹ thuật

### 1. Two-Phase Search Strategy
```
Phase 1: The Brain (LLM)     Phase 2: The Muscle (Ripgrep)
┌─────────────────────┐      ┌─────────────────────┐
│ Quyết định WHAT     │  →   │ Thực hiện HOW       │
│ to search           │      │ to search           │
│                     │      │                     │
│ Ví dụ: Tìm tất cả   │      │ Tốc độ: milliseconds│
│ nơi gọi hàm         │      │ Không rate limit    │
│ process_data()      │      │                     │
└─────────────────────┘      └─────────────────────┘
```

### 2. Iterative Refinement (Self-Learning Loop)
```
Search Code → Analyze Result → New Search Query
     ↑                              │
     └──────────────────────────────┘
```
- **Vấn đề**: Callers thường bị ẩn qua Facade, Alias, Dynamic Calls
- **Giải pháp**: LLM yêu cầu search thêm nếu chưa đủ
- **An toàn**: Giới hạn `MAX_SEARCH_ITERATIONS = 3`

### 3. File-by-File Processing
- Xử lý từng file và post comment ngay lập tức
- Developer nhận feedback nhanh, không cần đợi toàn bộ PR
- Graceful Degradation: Nếu LLM fail ở 1 file, các file khác vẫn được review

## Configuration

```python
# constants.py
MAX_SEARCH_ITERATIONS = 3      # Giới hạn loop
MAX_RESULTS_PER_QUERY = 20     # Giới hạn kết quả search
SEARCH_CONTEXT_LINES = 3       # Context cho mỗi match
CLONE_DEPTH = 1                # Shallow clone
CLONE_BLOB_LIMIT = "1m"        # Skip large files
CRITICAL_CALLER_THRESHOLD = 3  # >= 3 callers = critical
```

## Multi-language Support

- Output language configurable: `en`, `vi`, `ja`, `zh`
- Prompts có language instruction
- Labels được localize trong `locales.py`
