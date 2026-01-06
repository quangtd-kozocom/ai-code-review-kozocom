"""Internationalization (i18n) support for multi-language responses.

Supports: English (en), Vietnamese (vi), Japanese (ja)
"""

from typing import Literal

Language = Literal["en", "vi", "ja"]

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # GitHub publisher
        "suggestion_prefix": "**💡 Suggestion:**",
        # Success responses
        "fix_success": """\
## 🔧 Suggested Fix

```suggestion
{fixed_code}
```

**Explanation:** {explanation}

---

_Click "Commit suggestion" to apply this fix._
""",
        "explain_success": """\
## 🔍 Detailed Explanation

{content}

---

_If you still have questions, feel free to ask!_
""",
        "tests_success": """\
## 🧪 Generated Unit Tests

**Files analyzed:** {files_list}

{content}

---

_Copy these tests to your test file. Adjust imports if needed._
""",
        "help_message": """\
## 🤖 AI Reviewer Commands

| Command                    | Description                  |
| -------------------------- | ---------------------------- |
| `@reviewer fix this`       | Generate suggested fix       |
| `@reviewer explain`        | Explain the issue in detail  |
| `@reviewer generate tests` | Generate unit tests for PR   |
| `@reviewer help`           | Show this help               |

### Usage

**Fix & Explain:** Reply directly to a review comment

```
@reviewer fix this
```

**Generate Tests:** Comment anywhere in the PR

```
@reviewer generate tests
@reviewer generate tests for auth.py
```
""",
        # Error responses
        "error_no_parent_comment": """\
❌ **Review comment not found**

Please reply directly to a review comment \
(a comment on code, not a conversation comment).
""",
        "error_cannot_fetch_comment": "❌ Unable to fetch review comment information.",
        "error_cannot_read_file": "❌ Unable to read file content.",
        "error_cannot_generate_fix": "❌ Unable to generate fix. Please try again or fix manually.",
        "error_no_files_found": "❌ No changed files found in PR.",
        "error_no_matching_files": "❌ No matching files found{target_info}",
        "error_unknown_command": """\
❓ **Unknown command**

Try `@reviewer help` to see available commands.
""",
    },
    "vi": {
        # GitHub publisher
        "suggestion_prefix": "**💡 Gợi ý:**",
        # Success responses
        "fix_success": """\
## 🔧 Suggested Fix

```suggestion
{fixed_code}
```

**Giải thích:** {explanation}

---

_Click "Commit suggestion" để apply fix này._
""",
        "explain_success": """\
## 🔍 Giải Thích Chi Tiết

{content}

---

_Nếu vẫn chưa rõ, hãy hỏi thêm!_
""",
        "tests_success": """\
## 🧪 Generated Unit Tests

**Files analyzed:** {files_list}

{content}

---

_Copy tests này vào test file của bạn. Adjust imports nếu cần._
""",
        "help_message": """\
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
""",
        # Error responses
        "error_no_parent_comment": """\
❌ **Không tìm thấy review comment**

Vui lòng reply trực tiếp vào một review comment \
(comment trên code, không phải conversation comment).
""",
        "error_cannot_fetch_comment": "❌ Không thể lấy thông tin review comment.",
        "error_cannot_read_file": "❌ Không thể đọc nội dung file.",
        "error_cannot_generate_fix": (
            "❌ Không thể generate fix. Vui lòng thử lại hoặc sửa thủ công."
        ),
        "error_no_files_found": "❌ Không tìm thấy files changed trong PR.",
        "error_no_matching_files": "❌ Không tìm thấy file phù hợp{target_info}",
        "error_unknown_command": """\
❓ **Không hiểu command**

Thử `@reviewer help` để xem danh sách commands.
""",
    },
    "ja": {
        # GitHub publisher
        "suggestion_prefix": "**💡 提案:**",
        # Success responses
        "fix_success": """\
## 🔧 修正案

```suggestion
{fixed_code}
```

**説明:** {explanation}

---

_「Commit suggestion」をクリックしてこの修正を適用してください。_
""",
        "explain_success": """\
## 🔍 詳細説明

{content}

---

_ご不明な点があれば、お気軽にお問い合わせください。_
""",
        "tests_success": """\
## 🧪 生成されたユニットテスト

**分析したファイル:** {files_list}

{content}

---

_これらのテストをテストファイルにコピーしてください。必要に応じてインポートを調整してください。_
""",
        "help_message": """\
## 🤖 AI Reviewer コマンド

| コマンド                   | 説明                         |
| -------------------------- | ---------------------------- |
| `@reviewer fix this`       | 修正案を生成                 |
| `@reviewer explain`        | 問題を詳しく説明             |
| `@reviewer generate tests` | PRのユニットテストを生成     |
| `@reviewer help`           | このヘルプを表示             |

### 使い方

**Fix & Explain:** レビューコメントに直接返信

```
@reviewer fix this
```

**Generate Tests:** PR内のどこでもコメント

```
@reviewer generate tests
@reviewer generate tests for auth.py
```
""",
        # Error responses
        "error_no_parent_comment": """\
❌ **レビューコメントが見つかりません**

レビューコメント（会話コメントではなく、コード上のコメント）に\
直接返信してください。
""",
        "error_cannot_fetch_comment": "❌ レビューコメント情報を取得できません。",
        "error_cannot_read_file": "❌ ファイル内容を読み取れません。",
        "error_cannot_generate_fix": (
            "❌ 修正を生成できません。再試行するか、手動で修正してください。"
        ),
        "error_no_files_found": "❌ PRに変更されたファイルが見つかりません。",
        "error_no_matching_files": "❌ 一致するファイルが見つかりません{target_info}",
        "error_unknown_command": """\
❓ **不明なコマンド**

`@reviewer help` で利用可能なコマンドを確認してください。
""",
    },
}


def get_message(key: str, language: Language = "en", **kwargs: str) -> str:
    """
    Get a localized message by key.

    Args:
        key: Message key (e.g., "suggestion_prefix", "fix_success")
        language: Language code ("en", "vi", "ja")
        **kwargs: Format arguments for the message template

    Returns:
        Localized message string, falls back to English if not found
    """
    # Get messages for the requested language, fallback to English
    lang_messages = MESSAGES.get(language, MESSAGES["en"])
    message = lang_messages.get(key)

    # If key not found in requested language, try English
    if message is None:
        message = MESSAGES["en"].get(key, f"[Missing message: {key}]")

    # Format with kwargs if provided
    if kwargs:
        return message.format(**kwargs)
    return message


def get_language_name(language: Language) -> str:
    """Get human-readable language name."""
    names = {
        "en": "English",
        "vi": "Tiếng Việt",
        "ja": "日本語",
    }
    return names.get(language, "English")
