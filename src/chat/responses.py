"""Response templates for command handlers."""

# Success responses
FIX_SUCCESS = """\
## 🔧 Suggested Fix

```suggestion
{fixed_code}
```

**Giải thích:** {explanation}

---

_Click "Commit suggestion" để apply fix này._
"""

EXPLAIN_SUCCESS = """\
## 🔍 Giải Thích Chi Tiết

{content}

---

_Nếu vẫn chưa rõ, hãy hỏi thêm!_
"""

TESTS_SUCCESS = """\
## 🧪 Generated Unit Tests

**Files analyzed:** {files_list}

{content}

---

_Copy tests này vào test file của bạn. Adjust imports nếu cần._
"""

HELP_MESSAGE = """\
## 🤖 AI Reviewer Commands

| Command                    | Mô tả                        |
| -------------------------- | ---------------------------- |
| `@reviewer fix this`       | Tạo suggested fix cho issue  |
| `@reviewer explain`        | Giải thích chi tiết về issue |
| `@reviewer generate tests` | Tạo unit tests cho PR        |
| `@reviewer help`           | Hiện help này                |

### Cách sử dụng

**Fix & Explain:** Reply trực tiếp vào review comment

```
@reviewer fix this
```

**Generate Tests:** Comment ở bất kỳ đâu trong PR

```
@reviewer generate tests
@reviewer generate tests for auth.py
```
"""

# Error responses
ERROR_NO_PARENT_COMMENT = """\
❌ **Không tìm thấy review comment**

Vui lòng reply trực tiếp vào một review comment \
(comment trên code, không phải conversation comment).
"""

ERROR_CANNOT_FETCH_COMMENT = "❌ Không thể lấy thông tin review comment."
ERROR_CANNOT_READ_FILE = "❌ Không thể đọc nội dung file."
ERROR_CANNOT_GENERATE_FIX = "❌ Không thể generate fix. Vui lòng thử lại hoặc sửa thủ công."
ERROR_NO_FILES_FOUND = "❌ Không tìm thấy files changed trong PR."
ERROR_NO_MATCHING_FILES = "❌ Không tìm thấy file phù hợp{target_info}"
ERROR_UNKNOWN_COMMAND = """\
❓ **Không hiểu command**

Thử `@reviewer help` để xem danh sách commands.
"""
