"""Tests for fix command handler patterns."""

import pytest

from src.chat.handlers.fix import (
    RE_ENTITY,
    RE_FILE,
    RE_OLD_NEW,
    RE_RECOMMENDATION,
)


class TestFilePathPattern:
    """Test RE_FILE pattern extracts paths without backticks."""

    def test_extracts_path_with_backticks(self):
        comment = "File `app/Models/Order.php` has issues"
        matches = [m.group(1) for m in RE_FILE.finditer(comment)]
        assert matches == ["app/Models/Order.php"]

    def test_extracts_path_without_backticks(self):
        comment = "File app/Models/Order.php has issues"
        matches = [m.group(1) for m in RE_FILE.finditer(comment)]
        assert matches == ["app/Models/Order.php"]

    def test_extracts_multiple_paths(self):
        comment = """
        `app/Models/Order.php` (Định nghĩa hằng số)
        app/Services/OrderService.php (dòng 31)
        """
        matches = [m.group(1) for m in RE_FILE.finditer(comment)]
        assert matches == ["app/Models/Order.php", "app/Services/OrderService.php"]

    def test_handles_various_extensions(self):
        comment = "Files: `test.py`, `app.ts`, `main.java`, `util.go`"
        matches = [m.group(1) for m in RE_FILE.finditer(comment)]
        assert len(matches) == 4
        assert "test.py" in matches
        assert "app.ts" in matches


class TestRecommendationPattern:
    """Test RE_RECOMMENDATION pattern supports English and Vietnamese."""

    def test_extracts_english_recommendation(self):
        comment = """
        Issue found.

        Recommendation: Replace STATUS_PENDING with STATUS_AWAITING_PAYMENT.

        More text here.
        """
        match = RE_RECOMMENDATION.search(comment)
        assert match is not None
        assert "Replace STATUS_PENDING" in match.group(1)

    def test_extracts_vietnamese_recommendation(self):
        comment = """
        Vấn đề phát hiện.

        Khuyến Nghị: Cập nhật mã nguồn tại dòng 31 để sử dụng hằng số mới.

        Thêm text.
        """
        match = RE_RECOMMENDATION.search(comment)
        assert match is not None
        assert "Cập nhật mã nguồn" in match.group(1)

    def test_case_insensitive(self):
        comment = "RECOMMENDATION: Do this thing."
        match = RE_RECOMMENDATION.search(comment)
        assert match is not None

    def test_no_match_returns_none(self):
        comment = "No recommendation here."
        match = RE_RECOMMENDATION.search(comment)
        assert match is None


class TestEntityPattern:
    """Test RE_ENTITY pattern extracts entity names."""

    def test_extracts_english_constant(self):
        comment = "constant STATUS_PENDING was deleted"
        match = RE_ENTITY.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_PENDING"

    def test_extracts_vietnamese_constant(self):
        comment = "Hằng số STATUS_PENDING trong app/Models/Order.php"
        match = RE_ENTITY.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_PENDING"

    def test_extracts_with_backticks(self):
        comment = "constant `STATUS_PENDING` was removed"
        match = RE_ENTITY.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_PENDING"


class TestOldNewPattern:
    """Test RE_OLD_NEW pattern extracts replacement entity."""

    def test_extracts_english_replacement(self):
        comment = "replaced by STATUS_AWAITING_PAYMENT"
        match = RE_OLD_NEW.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_AWAITING_PAYMENT"

    def test_extracts_vietnamese_replacement(self):
        comment = "thay thế bằng STATUS_AWAITING_PAYMENT"
        match = RE_OLD_NEW.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_AWAITING_PAYMENT"

    def test_extracts_with_backticks(self):
        comment = "replaced by `STATUS_AWAITING_PAYMENT`"
        match = RE_OLD_NEW.search(comment)
        assert match is not None
        assert match.group(1) == "STATUS_AWAITING_PAYMENT"
