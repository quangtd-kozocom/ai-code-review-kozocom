# 🧪 Unit Test Generation Agent

> Agent chuyên biệt tự động generate unit tests cho code mới trong PR

**Độ ưu tiên:** 🔴 Cao  
**Độ phức tạp:** Cao  
**Tham khảo:** CodeRabbit Test Gen, Qodo Gen, EarlyAI, BaseRock AI

---

## 📋 Mô Tả

Một agent mới trong LangGraph workflow chuyên:

1. Phân tích functions/classes mới hoặc được sửa đổi
2. Tự động generate unit tests bao phủ happy path và edge cases
3. Post tests như suggestion hoặc commit trực tiếp vào PR

---

## 🎯 Mục Tiêu

- **Primary:** Tăng test coverage cho mỗi PR
- **Secondary:** Phát hiện edge cases developer có thể bỏ sót
- **Tertiary:** Giảm thời gian viết tests thủ công

---

## 💡 Cách Hoạt Động

### High-Level Flow

```
┌─────────────────┐
│  PR Code Changes│
│    (new/modified│
│    functions)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Identify      │
│  Testable Units │
│  (functions,    │
│   classes)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analyze        │
│  Dependencies   │
│  & Mocking Needs│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate Tests │
│  - Happy path   │
│  - Edge cases   │
│  - Error cases  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate Tests │
│  (syntax, AST)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Post to PR as  │
│  Suggestion or  │
│  New Commit     │
└─────────────────┘
```

### Integration Options

```
Option A: Post as PR Comment
─────────────────────────────
Developer reviews → Copies to test file manually

Option B: Create Test File Commit
─────────────────────────────
AI commits test file → Developer reviews in PR

Option C: On-Demand via Chat
─────────────────────────────
Developer requests: "@bot generate tests for auth.py"
```

---

## 🛠️ Technical Implementation

### 1. New Agent State

```python
# src/agents/state.py

class TestCase(BaseModel):
    """A generated test case."""
    name: str  # test_function_name
    description: str
    test_type: Literal["happy_path", "edge_case", "error_case"]
    code: str
    target_function: str
    target_file: str
    mocks_required: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)


class GraphState(TypedDict):
    # ... existing fields ...

    # NEW: Test generation
    generated_tests: list[TestCase]
    test_file_path: str | None
```

### 2. Test Generation Prompt

````python
# src/agents/prompts/test_generator.py

TEST_PROMPT = """You are an expert test engineer specializing in Python testing.

## Target Code:
File: {filename}
Language: {language}

```{language}
{code}
````

## Dependencies Detected:

{dependencies}

## Testing Framework: pytest

## Task:

Generate comprehensive unit tests for the function/class above.

## Requirements:

1. Use pytest conventions (test\_ prefix, fixtures)
2. Cover:
   - Happy path (normal operation)
   - Edge cases (boundary values, empty inputs)
   - Error cases (exceptions, invalid inputs)
3. Use appropriate mocking for external dependencies
4. Each test should be atomic and independent
5. Include descriptive docstrings

## Output (JSON):

{{
  "test_file_name": "test_filename.py",
  "imports": ["from x import y", "import pytest"],
  "fixtures": [
    {{
      "name": "sample_data",
      "code": "@pytest.fixture\\ndef sample_data():\\n    return {{...}}"
}}
],
"tests": [
{{
"name": "test_function_happy_path",
"description": "Test successful operation with valid input",
"type": "happy_path",
"code": "def test_function_happy_path():\\n ...",
"confidence": 0.95
}}
]
}}
"""

````

### 3. Test Generator Node

```python
# src/agents/nodes/test_generator.py

import ast
from typing import Any

async def run(state: GraphState) -> dict:
    """Generate unit tests for new/modified code."""
    llm = get_llm()
    all_tests: list[TestCase] = []

    for file in state["files"]:
        if not _is_testable_file(file):
            continue

        # Extract functions and classes from the diff
        testable_units = _extract_testable_units(file)

        for unit in testable_units:
            # Analyze dependencies for mocking
            dependencies = _analyze_dependencies(unit)

            prompt = TEST_PROMPT.format(
                filename=file.filename,
                language=file.language or "python",
                code=unit["code"],
                dependencies=_format_dependencies(dependencies),
            )

            response = await llm.ainvoke(prompt)
            test_data = _parse_test_response(response.content)

            if test_data:
                for test in test_data.get("tests", []):
                    all_tests.append(TestCase(
                        name=test["name"],
                        description=test["description"],
                        test_type=test["type"],
                        code=test["code"],
                        target_function=unit["name"],
                        target_file=file.filename,
                        confidence=test.get("confidence", 0.8),
                    ))

    # Determine test file path
    test_file_path = _generate_test_file_path(state["files"])

    log.info("Tests generated", count=len(all_tests))
    return {
        "generated_tests": all_tests,
        "test_file_path": test_file_path,
    }


def _is_testable_file(file: FileChange) -> bool:
    """Check if file should have tests generated."""
    # Skip test files themselves
    if "test_" in file.filename or "_test" in file.filename:
        return False
    # Skip config, migration files
    if any(x in file.filename for x in ["__init__", "config", "migration"]):
        return False
    # Only Python for now
    return file.language == "python"


def _extract_testable_units(file: FileChange) -> list[dict]:
    """Parse diff to extract new/modified functions and classes."""
    units = []

    # Parse the patch to find added lines
    added_code = _extract_added_code(file.patch)

    try:
        tree = ast.parse(added_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private methods (optional)
                if not node.name.startswith('_'):
                    units.append({
                        "name": node.name,
                        "type": "function",
                        "code": ast.unparse(node),
                    })
            elif isinstance(node, ast.ClassDef):
                units.append({
                    "name": node.name,
                    "type": "class",
                    "code": ast.unparse(node),
                })
    except SyntaxError:
        log.warning("Could not parse code for test extraction")

    return units


def _analyze_dependencies(unit: dict) -> list[dict]:
    """Analyze external dependencies that need mocking."""
    dependencies = []

    code = unit["code"]

    # Simple heuristic: look for common patterns
    patterns = [
        ("httpx", "HTTP client"),
        ("requests", "HTTP client"),
        ("database", "Database"),
        ("redis", "Redis"),
        ("boto3", "AWS"),
        ("datetime.now", "Datetime"),
    ]

    for pattern, dep_type in patterns:
        if pattern.lower() in code.lower():
            dependencies.append({
                "name": pattern,
                "type": dep_type,
                "mock_suggestion": f"Use pytest-mock or unittest.mock for {pattern}",
            })

    return dependencies
````

### 4. Test Publisher Options

````python
# src/agents/nodes/test_publisher.py

async def run(state: GraphState) -> dict:
    """Publish generated tests to PR."""
    tests = state["generated_tests"]
    test_file_path = state["test_file_path"]
    ctx = state["context"]

    if not tests:
        return {}

    # Format all tests into a single file
    test_content = _format_test_file(tests)

    # Option A: Post as PR comment with code block
    comment = _format_tests_as_comment(tests, test_content)

    github = GitHubService(ctx.installation_id)

    await github.create_pr_comment(
        owner=ctx.owner,
        repo=ctx.repo,
        pr_number=ctx.pr_number,
        body=comment,
    )

    # Option B (advanced): Create commit with test file
    # await github.create_file_in_pr(
    #     owner=ctx.owner,
    #     repo=ctx.repo,
    #     pr_number=ctx.pr_number,
    #     path=test_file_path,
    #     content=test_content,
    #     message="🧪 Add AI-generated tests",
    # )

    return {}


def _format_tests_as_comment(tests: list[TestCase], content: str) -> str:
    """Format tests as a PR comment."""

    happy = sum(1 for t in tests if t.test_type == "happy_path")
    edge = sum(1 for t in tests if t.test_type == "edge_case")
    error = sum(1 for t in tests if t.test_type == "error_case")

    comment = """## 🧪 AI-Generated Unit Tests

I've generated **{total}** test cases for this PR:

| Type | Count |
|------|-------|
| ✅ Happy Path | {happy} |
| 🔀 Edge Cases | {edge} |
| ❌ Error Cases | {error} |

### Generated Test File

<details>
<summary>Click to expand test code</summary>

```python
{content}
````

</details>

---

_Copy this code to your test file, or ask me to commit it directly._
_Run with: `pytest {test_file_path}`_
""".format(
total=len(tests),
happy=happy,
edge=edge,
error=error,
content=content,
test*file_path="tests/test*..."
)

    return comment

````

### 5. Graph Integration

```python
# src/agents/graph.py

def create_graph() -> StateGraph:
    g = StateGraph(GraphState)

    # Existing nodes...
    g.add_node("extract", context_extractor.run)
    g.add_node("security", security_agent.run)
    g.add_node("style", style_agent.run)
    g.add_node("logic", logic_agent.run)
    g.add_node("aggregate", aggregator.run)
    g.add_node("generate_fixes", fix_generator.run)
    g.add_node("publish", github_publisher.run)
    g.add_node("notify", slack_reporter.run)

    # NEW: Test generation (parallel with main review)
    g.add_node("generate_tests", test_generator.run)
    g.add_node("publish_tests", test_publisher.run)

    # Flow - tests run in parallel
    g.set_entry_point("extract")

    # Main review flow
    g.add_edge("extract", "security")
    g.add_edge("extract", "style")
    g.add_edge("extract", "logic")

    # Test generation flow (parallel)
    g.add_edge("extract", "generate_tests")

    # Fan-in
    g.add_edge("security", "aggregate")
    g.add_edge("style", "aggregate")
    g.add_edge("logic", "aggregate")
    g.add_edge("aggregate", "generate_fixes")
    g.add_edge("generate_fixes", "publish")

    # Test publishing after tests generated
    g.add_edge("generate_tests", "publish_tests")

    # Both paths lead to notify
    g.add_edge("publish", "notify")
    g.add_edge("publish_tests", "notify")

    g.add_edge("notify", END)

    return g.compile()
````

---

## 📊 Test Coverage Analysis

### Coverage Report Format

```markdown
## 📊 Test Coverage Impact

| File     | Before | After (Projected) | Change  |
| -------- | ------ | ----------------- | ------- |
| auth.py  | 45%    | 82%               | +37% ⬆️ |
| utils.py | 60%    | 78%               | +18% ⬆️ |

**Untested Lines Addressed:** 15
**New Edge Cases Covered:** 8
```

---

## ✅ Acceptance Criteria

1. [ ] Generate tests cho Python functions mới
2. [ ] Coverage happy path, edge cases, errors
3. [ ] Detect và suggest mocks cho external deps
4. [ ] Tests có thể copy-paste và chạy ngay
5. [ ] Format đúng pytest conventions
6. [ ] Confidence score cho mỗi test

---

## 📊 Metrics

| Metric                               | Target       |
| ------------------------------------ | ------------ |
| Tests generated per PR               | 5-15         |
| Valid test rate (runs without error) | > 90%        |
| Edge case coverage                   | > 70%        |
| Time to generate                     | < 30 seconds |

---

## ⚠️ Limitations & Risks

1. **Complex dependencies:** Mock generation có thể không chính xác
2. **Business logic:** AI không hiểu full business context
3. **Integration tests:** Scope này chỉ unit tests
4. **Language support:** Bắt đầu với Python, mở rộng sau

---

## 🔮 Future Enhancements

1. **Multi-language:** JavaScript/TypeScript, Go, Java
2. **Integration tests:** E2E test generation
3. **Coverage integration:** Tích hợp với coverage tools
4. **Test quality scoring:** Đánh giá quality của generated tests
5. **Mutation testing:** Validate test effectiveness
