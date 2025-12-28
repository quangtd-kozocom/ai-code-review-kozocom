# 🤖 Multi-Model Review

> Sử dụng nhiều AI models khác nhau để cross-validate reviews

**Độ ưu tiên:** 🟢 Thấp  
**Độ phức tạp:** Trung bình  
**Tham khảo:** CodeRabbit multi-model, MCP multi-model review server

---

## 📋 Mô Tả

Chạy review qua nhiều models (GPT-4, Claude, Gemini) và:

1. Cross-validate findings
2. Consolidate duplicates
3. Increase confidence cho issues found by multiple models
4. Reduce false positives qua consensus

---

## 🎯 Mục Tiêu

- **Primary:** Higher accuracy qua consensus
- **Secondary:** Reduce false positives
- **Tertiary:** Leverage specialized models (Claude for logic, GPT for security)

---

## 💡 Model Specialization

| Model       | Specialty            | Use For        |
| ----------- | -------------------- | -------------- |
| GPT-4       | Security, general    | Security agent |
| Claude Opus | Logic, reasoning     | Logic agent    |
| Gemini Pro  | Code style, patterns | Style agent    |

---

## 🛠️ Technical Implementation

### Multi-Model Router

```python
# src/core/llm.py

class MultiModelRouter:
    """Route review tasks to appropriate models."""

    ROUTING = {
        "security": ["gpt-4", "claude-3-opus"],
        "logic": ["claude-3-opus", "gpt-4"],
        "style": ["gemini-pro", "gpt-4-mini"],
    }

    async def invoke(self, task_type: str, prompt: str) -> list[Response]:
        """Get responses from multiple models."""
        models = self.ROUTING[task_type]
        responses = await asyncio.gather(*[
            self.get_model(m).ainvoke(prompt) for m in models
        ])
        return responses
```

### Consensus Engine

```python
# src/agents/nodes/consensus.py

async def consolidate_findings(findings: list[list[Finding]]) -> list[Finding]:
    """Merge findings from multiple models."""
    merged = []

    for finding_group in cluster_by_location(findings):
        if len(finding_group) > 1:
            # Multiple models agree - high confidence
            merged.append(finding_group[0].with_confidence(0.95))
        else:
            # Single model - keep original confidence
            merged.append(finding_group[0])

    return merged
```

---

## ✅ Acceptance Criteria

1. [ ] Support multiple LLM providers
2. [ ] Consensus increases confidence
3. [ ] Single-model findings flagged appropriately
4. [ ] Cost tracking per model

---

## 📊 Metrics

| Metric                   | Target               |
| ------------------------ | -------------------- |
| False positive reduction | -40% vs single model |
| Latency increase         | < 2x single model    |
| Cost increase            | < 1.5x single model  |
