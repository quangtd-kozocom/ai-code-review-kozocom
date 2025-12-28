# 💻 CLI Tool

> Command-line tool để chạy AI code review locally trước khi push

**Độ ưu tiên:** 🟢 Thấp  
**Độ phức tạp:** Trung bình  
**Tham khảo:** CodeRabbit CLI, Qodo Command

---

## 📋 Mô Tả

CLI tool cho phép developers:

1. Review uncommitted changes locally
2. Get instant feedback trong terminal
3. Fix issues trước khi push
4. Integrate với CI/CD pipelines

---

## 🎯 Mục Tiêu

- **Primary:** Shift-left reviews - phát hiện issues sớm hơn
- **Secondary:** Faster feedback loop
- **Tertiary:** CI/CD gate integration

---

## 💡 Usage Examples

```bash
# Review current changes
$ reviewer review

# Review specific files
$ reviewer review src/auth.py src/utils.py

# Review with specific checks
$ reviewer review --security-only

# Output as JSON for CI
$ reviewer review --format json --output report.json

# Interactive mode
$ reviewer review --interactive
```

---

## 🛠️ Technical Implementation

### CLI Entry Point

```python
# src/cli/main.py
import click

@click.group()
def cli():
    """AI Code Reviewer CLI"""
    pass

@cli.command()
@click.argument("files", nargs=-1)
@click.option("--format", type=click.Choice(["text", "json"]))
def review(files, format):
    """Review code changes."""
    diff = get_local_diff(files)
    result = run_review(diff)
    output(result, format)
```

### Local Review Engine

```python
# src/cli/engine.py

async def run_local_review(diff: str) -> ReviewResult:
    """Run review without GitHub integration."""
    from ..agents.graph import create_graph

    state = {
        "files": parse_diff(diff),
        "context": LocalContext(),
    }

    result = await graph.ainvoke(state)
    return format_for_terminal(result)
```

---

## ✅ Acceptance Criteria

1. [ ] `pip install ai-reviewer` works
2. [ ] Review uncommitted changes
3. [ ] Output in text và JSON formats
4. [ ] Exit codes for CI integration
5. [ ] Interactive mode với fix suggestions

---

## 📊 Metrics

| Metric              | Target       |
| ------------------- | ------------ |
| Review time (local) | < 10 seconds |
| Install size        | < 50 MB      |
