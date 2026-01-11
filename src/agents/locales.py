# src/agents/locales.py
"""Localization strings for review output."""

LOCALES = {
    "en": {
        # Labels
        "breaking_change": "Breaking Change Detected",
        "problem": "Problem",
        "context_used": "Context Used",
        "dependencies": "Dependencies",
        "analyzed": "analyzed",
        "external_files": "External Files",
        "affected": "affected",
        "file": "File",
        "break_reason": "Break Reason",
        "recommendation": "Recommendation",
        "what_changed": "What changed",
        "affected_files": "Affected Files",
        # Recommendations
        "rec_signature": "Add a default value for the new parameter, or update all {count} caller(s) to pass the required argument.",
        "rec_deleted": "Restore the {entity_type} or update all {count} caller(s) to use an alternative.",
        "rec_visibility": "Keep the {entity_type} public, or refactor {count} caller(s) to use a public API.",
        "rec_default": "Review and update all {count} affected caller(s).",
    },
    "vi": {
        # Labels
        "breaking_change": "Phát Hiện Thay Đổi Phá Vỡ",
        "problem": "Vấn Đề",
        "context_used": "Ngữ Cảnh Sử Dụng",
        "dependencies": "Phụ Thuộc",
        "analyzed": "đã phân tích",
        "external_files": "File Bên Ngoài",
        "affected": "bị ảnh hưởng",
        "file": "File",
        "break_reason": "Lý Do Lỗi",
        "recommendation": "Khuyến Nghị",
        "what_changed": "Thay đổi",
        "affected_files": "File Bị Ảnh Hưởng",
        # Recommendations
        "rec_signature": "Thêm giá trị mặc định cho tham số mới, hoặc cập nhật tất cả {count} caller(s) để truyền tham số bắt buộc.",
        "rec_deleted": "Khôi phục {entity_type} hoặc cập nhật tất cả {count} caller(s) để sử dụng phương án thay thế.",
        "rec_visibility": "Giữ {entity_type} ở chế độ public, hoặc refactor {count} caller(s) để sử dụng public API.",
        "rec_default": "Xem xét và cập nhật tất cả {count} caller(s) bị ảnh hưởng.",
    },
    "ja": {
        # Labels
        "breaking_change": "破壊的変更を検出",
        "problem": "問題",
        "context_used": "使用されたコンテキスト",
        "dependencies": "依存関係",
        "analyzed": "分析済み",
        "external_files": "外部ファイル",
        "affected": "影響あり",
        "file": "ファイル",
        "break_reason": "破損理由",
        "recommendation": "推奨事項",
        "what_changed": "変更内容",
        "affected_files": "影響を受けるファイル",
        # Recommendations
        "rec_signature": "新しいパラメータにデフォルト値を追加するか、{count}個の呼び出し元を更新して必須引数を渡してください。",
        "rec_deleted": "{entity_type}を復元するか、{count}個の呼び出し元を代替手段を使用するように更新してください。",
        "rec_visibility": "{entity_type}をpublicのままにするか、{count}個の呼び出し元をpublic APIを使用するようにリファクタリングしてください。",
        "rec_default": "影響を受ける{count}個の呼び出し元をすべて確認して更新してください。",
    },
    "zh": {
        # Labels
        "breaking_change": "检测到破坏性更改",
        "problem": "问题",
        "context_used": "使用的上下文",
        "dependencies": "依赖项",
        "analyzed": "已分析",
        "external_files": "外部文件",
        "affected": "受影响",
        "file": "文件",
        "break_reason": "破坏原因",
        "recommendation": "建议",
        "what_changed": "更改内容",
        "affected_files": "受影响的文件",
        # Recommendations
        "rec_signature": "为新参数添加默认值，或更新所有{count}个调用者以传递必需的参数。",
        "rec_deleted": "恢复{entity_type}或更新所有{count}个调用者以使用替代方案。",
        "rec_visibility": "保持{entity_type}为public，或重构{count}个调用者以使用public API。",
        "rec_default": "检查并更新所有{count}个受影响的调用者。",
    },
}


def get_locale(lang: str = "en") -> dict[str, str]:
    """Get locale strings for a language."""
    return LOCALES.get(lang, LOCALES["en"])


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Translate a key with optional formatting."""
    locale = get_locale(lang)
    text = locale.get(key, LOCALES["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text
