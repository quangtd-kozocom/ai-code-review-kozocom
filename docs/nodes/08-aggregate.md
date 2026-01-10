# Aggregate Node

## 📋 Tổng quan

Node cuối cùng trước khi publish, thực hiện aggregate, deduplicate và finalize review comments.

**Đặc điểm:** Pure data processing, không có LLM hay external API calls.

---

## 🎯 Chức năng chính

1. **Filter by severity** - Chỉ giữ lại critical và warning
2. **Filter by confidence** - Loại bỏ findings có confidence thấp
3. **Deduplicate** - Xóa duplicate comments
4. **Group related issues** - Gộp các issues liên quan
5. **Sort by priority** - Sắp xếp theo severity và confidence
6. **Apply limits** - Giới hạn số comments per file
7. **Generate summary** - Tạo summary markdown

---

## 📥 Input (State)

Node nhận vào `ReviewState` với các trường:

| Field | Type | Mô tả |
|-------|------|-------|
| `comments` | `list[ReviewComment]` | Raw comments từ review nodes |
| `review_failures` | `list[dict]` | Functions failed to review |
| `repo_config` | `ReviewerConfig` | Config của repository |

---

## 📤 Output (State Updates)

Node trả về dict cập nhật state với:

| Field | Type | Mô tả |
|-------|------|-------|
| `final_comments` | `list[ReviewComment]` | Finalized comments ready to publish |
| `summary` | `str` | Markdown summary của review |

---

## 🔄 Quy trình xử lý

```mermaid
graph TD
    A[Nhận ReviewState] --> B[Get comments & config]
    B --> C{Có comments?}
    C -->|No| D[Return empty with "No issues"]
    C -->|Yes| E[Filter by severity]
    E --> F[Filter by confidence]
    F --> G[Deduplicate]
    G --> H[Group related issues]
    H --> I[Sort by priority]
    I --> J[Apply per-file limits]
    J --> K[Generate summary]
    K --> L[Return final_comments & summary]
```

---

## 🛠️ Processing Steps

### Step 1: Filter by Severity

Chỉ giữ lại **critical** và **warning**:

```python
def _filter_by_severity(comments):
    """Keep only critical and warning."""
    allowed = {"critical", "warning"}
    return [c for c in comments if c.severity in allowed]
```

**Rationale**:
- **Info** và **suggestion** tạo noise
- Focus vào issues quan trọng
- Giảm cognitive load cho reviewer

**Before**: 50 comments (10 critical, 15 warning, 20 info, 5 suggestion)
**After**: 25 comments (10 critical, 15 warning)

---

### Step 2: Filter by Confidence

Loại bỏ findings có confidence < threshold:

```python
def _filter_by_confidence(comments, threshold):
    """Filter by confidence threshold."""
    return [c for c in comments if c.confidence >= threshold]
```

**Default threshold**: 0.7 (configurable)

**Confidence levels**:
- **0.9-1.0**: Very confident, likely correct
- **0.7-0.9**: Confident, worth reviewing
- **0.5-0.7**: Uncertain, might be false positive
- **< 0.5**: Low confidence, likely false positive

**Example**:
```python
# Before
comments = [
    Comment(severity="critical", confidence=0.95, ...),
    Comment(severity="warning", confidence=0.85, ...),
    Comment(severity="warning", confidence=0.60, ...),  # Removed
    Comment(severity="critical", confidence=0.50, ...),  # Removed
]

# After (threshold=0.7)
comments = [
    Comment(severity="critical", confidence=0.95, ...),
    Comment(severity="warning", confidence=0.85, ...),
]
```

---

### Step 3: Deduplicate

Xóa duplicate comments dựa trên `(file, line, category)`:

```python
def _deduplicate(comments):
    """Remove duplicates by (file, line, category)."""
    seen = set()
    unique = []
    
    for c in comments:
        key = (c.file, c.line, c.category)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    
    return unique
```

**Example**:
```python
# Before
[
    Comment(file="user.py", line=15, category="logic", message="Missing validation"),
    Comment(file="user.py", line=15, category="logic", message="No input check"),  # Duplicate
    Comment(file="user.py", line=20, category="security", message="SQL injection"),
]

# After
[
    Comment(file="user.py", line=15, category="logic", message="Missing validation"),
    Comment(file="user.py", line=20, category="security", message="SQL injection"),
]
```

---

### Step 4: Group Related Issues

Gộp semantically related issues thành một comment:

```python
def _group_related_issues(comments):
    """Group semantically related issues."""
    
    # Classify each comment by issue type
    grouped = defaultdict(list)
    
    for comment in comments:
        issue_type = _classify_issue_type(comment.message)
        key = (comment.file, issue_type)
        grouped[key].append(comment)
    
    result = []
    
    for (file, issue_type), group in grouped.items():
        if len(group) == 1:
            result.append(group[0])
        elif len(group) <= 5:
            # Merge into single comment
            merged = _merge_comments(group, issue_type)
            result.append(merged)
        else:
            # Too many, keep top 3
            sorted_group = sorted(group, key=lambda c: c.confidence, reverse=True)
            result.extend(sorted_group[:3])
    
    return result
```

#### Issue Type Classification:

```python
ISSUE_TYPE_PATTERNS = {
    "input_validation": [
        "input", "validate", "sanitize", "check",
        "None", "null", "empty", "missing"
    ],
    "error_handling": [
        "exception", "error", "try", "catch",
        "raise", "throw", "handle"
    ],
    "resource_management": [
        "close", "cleanup", "dispose", "leak",
        "file", "connection", "resource"
    ],
    "null_safety": [
        "None", "null", "undefined", "optional",
        "AttributeError", "TypeError"
    ],
    "bounds_checking": [
        "index", "bounds", "range", "array",
        "out of", "overflow"
    ],
}
```

#### Merged Comment Format:

```markdown
**Multiple Input Validation Issues Found:**

1. Line 15: Missing email validation
   - Fix: Add email format check

2. Line 20: No null check for name parameter
   - Fix: if not name: raise ValueError()

3. Line 25: Age parameter not validated
   - Fix: Ensure age > 0
```

---

### Step 5: Sort by Priority

Sort theo severity (critical first), sau đó confidence (high first):

```python
def _sort_by_priority(comments):
    """Sort by severity, then confidence."""
    
    severity_priority = {
        "critical": 0,
        "warning": 1,
        "info": 2,
        "suggestion": 3,
    }
    
    return sorted(
        comments,
        key=lambda c: (
            severity_priority.get(c.severity, 99),
            -c.confidence  # Negative for descending
        )
    )
```

**Result**:
1. Critical (confidence 0.95)
2. Critical (confidence 0.85)
3. Warning (confidence 0.90)
4. Warning (confidence 0.75)

---

### Step 6: Apply Per-File Limits

Limit số comments per file để tránh overwhelming:

```python
def _limit_per_file(comments, limit):
    """Keep only top N comments per file."""
    
    by_file = defaultdict(list)
    
    for c in comments:
        if len(by_file[c.file]) < limit:
            by_file[c.file].append(c)
    
    return [c for file_comments in by_file.values() for c in file_comments]
```

**Default limit**: 10 comments/file

**Example**:
```
user.py: 15 comments → keep top 10
payment.py: 5 comments → keep all 5
order.py: 8 comments → keep all 8
```

---

### Step 7: Generate Summary

Create markdown summary với statistics:

```python
def _generate_summary(comments, language, review_failures):
    """Generate markdown summary."""
    
    counts = Counter(c.severity for c in comments)
    
    template = SUMMARY_TEMPLATES[language]
    
    summary = template.format(
        critical=counts.get("critical", 0),
        warning=counts.get("warning", 0),
        info=counts.get("info", 0),
        suggestion=counts.get("suggestion", 0),
        total=len(comments),
    )
    
    # Add failure info
    if review_failures:
        summary += f"\n\n⚠️ **Note**: {len(review_failures)} function(s) could not be reviewed due to errors.\n"
    
    return summary
```

#### Summary Templates:

**English**:
```markdown
## 🤖 AI Code Review

| Severity | Count |
|----------|-------|
| 🔴 Critical | 3 |
| 🟡 Warning | 5 |
| 🔵 Info | 0 |
| 💡 Suggestion | 0 |

**Total: 8 comments**
```

**Vietnamese**:
```markdown
## 🤖 AI Code Review

| Mức độ | Số lượng |
|--------|----------|
| 🔴 Critical | 3 |
| 🟡 Warning | 5 |
| 🔵 Info | 0 |
| 💡 Suggestion | 0 |

**Tổng cộng: 8 nhận xét**
```

**Japanese**:
```markdown
## 🤖 AI Code Review

| 深刻度 | 件数 |
|--------|------|
| 🔴 Critical | 3 |
| 🟡 Warning | 5 |
| 🔵 Info | 0 |
| 💡 Suggestion | 0 |

**合計: 8 件**
```

---

## 📊 Logging & Metrics

```python
# Start
log.info("aggregator.started",
    raw_count=len(comments),
    failures=len(review_failures),
)

# After severity filter
log.info("aggregator.after_severity_filter",
    count=len(comments),
)

# After confidence filter
log.info("aggregator.after_confidence_filter",
    count=len(comments),
    threshold=threshold,
)

# After grouping
log.info("aggregator.after_grouping",
    count=len(comments),
)

# Complete
log.info("aggregator.complete",
    final_count=len(comments),
    critical=sum(1 for c in comments if c.severity == "critical"),
    warning=sum(1 for c in comments if c.severity == "warning"),
    failures=len(review_failures),
)
```

---

## ⚡ Performance

- **Pure data processing**: Không có I/O
- **O(n log n) complexity**: Chủ yếu do sorting
- **Typical time**: < 50ms
- **Memory efficient**: In-place filtering

---

## 🚨 Error Handling

```python
# No comments
if not comments and not review_failures:
    return {
        "final_comments": [],
        "summary": "## 🤖 AI Code Review\n\n✅ No issues found!",
    }

# Invalid severity
if c.severity not in allowed_severities:
    log.warning("Invalid severity", severity=c.severity)
    c.severity = "warning"  # Default
```

---

## 🔗 Next Node

Sau node này, state được chuyển đến:
- **github_publisher** - Post review to GitHub

---

## 📝 Example

### Input state:
```python
{
    "comments": [
        ReviewComment(file="user.py", line=15, severity="critical", confidence=0.95, ...),
        ReviewComment(file="user.py", line=15, severity="critical", confidence=0.85, ...),  # Duplicate
        ReviewComment(file="user.py", line=20, severity="warning", confidence=0.75, ...),
        ReviewComment(file="user.py", line=25, severity="info", confidence=0.90, ...),  # Filtered
        ReviewComment(file="user.py", line=30, severity="warning", confidence=0.60, ...),  # Low confidence
        ReviewComment(file="payment.py", line=10, severity="critical", confidence=0.90, ...),
    ],
    "review_failures": [
        {"function": "complex_algo", "error": "Timeout"}
    ],
    "repo_config": ReviewerConfig(
        confidence_threshold=0.7,
        max_comments_per_file=10,
        language="en"
    )
}
```

### Processing:

1. **Severity filter**: 5 comments (removed "info")
2. **Confidence filter**: 4 comments (removed 0.60)
3. **Deduplicate**: 3 comments (removed duplicate at user.py:15)
4. **Group**: 3 comments (no grouping needed)
5. **Sort**: [user.py:15 critical 0.95, payment.py:10 critical 0.90, user.py:20 warning 0.75]
6. **Limit**: All kept (< 10 per file)

### Output state:
```python
{
    "final_comments": [
        ReviewComment(file="user.py", line=15, severity="critical", confidence=0.95, ...),
        ReviewComment(file="payment.py", line=10, severity="critical", confidence=0.90, ...),
        ReviewComment(file="user.py", line=20, severity="warning", confidence=0.75, ...),
    ],
    "summary": """
## 🤖 AI Code Review

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟡 Warning | 1 |
| 🔵 Info | 0 |
| 💡 Suggestion | 0 |

**Total: 3 comments**

---

⚠️ **Note**: 1 function(s) could not be reviewed due to errors.
    """
}
```

---

## 💡 Configuration

```python
class ReviewerConfig:
    # Filtering
    confidence_threshold: float = 0.7
    include_info_severity: bool = False
    include_suggestion_severity: bool = False
    
    # Limits
    max_comments_per_file: int = 10
    max_total_comments: int = 50
    
    # Grouping
    enable_issue_grouping: bool = True
    max_issues_per_group: int = 5
    
    # Summary
    language: Language = "en"  # "en", "vi", "ja"
```

---

## 🎯 Quality Metrics

After aggregation:

```python
{
    "raw_comments": 50,
    "after_severity_filter": 25,
    "after_confidence_filter": 20,
    "after_dedup": 18,
    "after_grouping": 15,
    "final_comments": 15,
    
    "filters_applied": {
        "severity": 25,  # Removed 25
        "confidence": 5,  # Removed 5
        "duplicate": 2,   # Removed 2
        "grouped": 3,     # Merged 3 into 1
    }
}
```

---

## 🔮 Future Enhancements

1. **ML-based grouping**: Learn which issues to group
2. **Smart limits**: Dynamic per-file limits based on file size
3. **Severity adjustment**: Auto-adjust based on context
4. **Custom templates**: User-defined summary templates
