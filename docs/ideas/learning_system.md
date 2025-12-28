# 🧠 Learning & Feedback System

> Hệ thống học từ feedback của developers để cải thiện reviews

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Cao  
**Tham khảo:** Sourcery Learning, CodeRabbit adaptive reviews

---

## 📋 Mô Tả

Hệ thống học từ:

1. Accepted vs rejected suggestions
2. Developer reactions (👍/👎)
3. Dismissed false positives
4. Frequently ignored patterns

---

## 🎯 Mục Tiêu

- **Primary:** Giảm false positives theo thời gian
- **Secondary:** Adapt to team's coding style
- **Tertiary:** Personalized reviews per developer

---

## 💡 Learning Signals

| Signal           | Weight | Example                          |
| ---------------- | ------ | -------------------------------- |
| Fix accepted     | +1.0   | Developer applied suggested fix  |
| Comment resolved | +0.5   | Issue marked resolved            |
| 👎 reaction      | -0.5   | Developer disagrees              |
| Dismissed        | -0.3   | Comment dismissed without action |

---

## 🛠️ Technical Implementation

### Feedback Collection

```python
# src/feedback/collector.py

async def collect_feedback(webhook_payload: dict):
    """Collect learning signals from GitHub events."""

    if webhook_payload["action"] == "dismissed":
        # Comment was dismissed
        record_negative_feedback(comment_id, "dismissed")

    elif webhook_payload["action"] == "resolved":
        # Thread resolved
        record_positive_feedback(comment_id, "resolved")
```

### Model Adjustment

```python
# src/feedback/learner.py

class ReviewLearner:
    """Adjust review behavior based on feedback."""

    def get_confidence_adjustment(self, pattern: str, repo: str) -> float:
        """Adjust confidence for patterns based on history."""
        history = self.db.get_pattern_history(pattern, repo)

        accept_rate = history.accepted / history.total
        return accept_rate - 0.5  # Adjust confidence
```

---

## ✅ Acceptance Criteria

1. [ ] Track accepted/rejected suggestions
2. [ ] Adjust confidence based on history
3. [ ] Per-repo learning
4. [ ] Dashboard showing improvement metrics

---

## 📊 Metrics

| Metric                   | Target             |
| ------------------------ | ------------------ |
| False positive reduction | -30% after 1 month |
| Acceptance rate increase | +20%               |
