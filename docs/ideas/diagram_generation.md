# 📊 Sequence Diagram Generation

> Tự động tạo sequence diagrams cho code changes trong PR

**Độ ưu tiên:** 🟡 Trung bình  
**Độ phức tạp:** Thấp  
**Tham khảo:** CodeRabbit Sequence Diagrams, Greptile, Mermaid

---

## 📋 Mô Tả

Tự động tạo Mermaid sequence diagrams để visualize:

1. Control flow của functions mới
2. Interactions giữa các services/classes
3. API call chains
4. Database operations flow

---

## 🎯 Mục Tiêu

- **Primary:** Giúp reviewer hiểu nhanh code flow
- **Secondary:** Documentation tự động
- **Tertiary:** Phát hiện complex/inefficient patterns

---

## 💡 Example Output

### PR Comment Format

```markdown
## 📊 Code Flow Visualization

**Key Observations:**

- 🔄 3 database calls in sequence (consider batching)
- ⚡ Redis caching added for performance
- ⚠️ No error handling for DB connection failure
```

---

## 🛠️ Technical Implementation

### Diagram Generator Agent

```python
# src/agents/nodes/diagram_generator.py

DIAGRAM_PROMPT = """Create a Mermaid sequence diagram showing:
1. Main actors/participants
2. Method calls and sequence
3. Conditional flows (alt/else)

Output JSON with diagram and observations.
"""

async def run(state: GraphState) -> dict:
    """Generate sequence diagrams for significant code changes."""
    llm = get_llm()
    diagrams = []

    for file in state["files"]:
        if file.additions >= 10 and file.language:
            prompt = DIAGRAM_PROMPT.format(code=file.patch)
            response = await llm.ainvoke(prompt)
            # Parse and add diagram

    return {"diagrams": diagrams}
```

---

## ✅ Acceptance Criteria

1. [ ] Generate diagrams cho files với > 10 lines added
2. [ ] Mermaid syntax renders correctly trong GitHub
3. [ ] Include observations về code quality
4. [ ] Complexity score giúp identify complex changes

---

## 📊 Metrics

| Metric              | Target |
| ------------------- | ------ |
| Diagrams per PR     | 1-3    |
| Render success rate | 100%   |
