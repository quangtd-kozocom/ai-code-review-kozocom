# 🧪 Unit Test Generation

> **(✅ IMPLEMENTED)** - Command `@reviewer tests` đã được implement

**Status:** ✅ Đã hoàn thành  
**Implementation:** `src/chat/handler.py` → `GenerateTestsCommandHandler`

---

## 📋 Đã Implement

### Command Usage

```markdown
# Generate tests for all changed files

@reviewer tests

# Generate tests for specific file

@reviewer tests for auth.py
```

### How It Works

1. Developer comments `@reviewer tests` hoặc `@reviewer tests for <file>`
2. Bot fetches PR files và filters testable files
3. LLM generates pytest unit tests
4. Bot posts tests as PR comment

### Implementation

```python
# src/chat/handler.py

class GenerateTestsCommandHandler(BaseCommandHandler):
    """Generate unit tests for PR changes."""

    MAX_FILES = 3  # Limit files to avoid token limits

    async def execute(self, ctx: CommandContext) -> str:
        # 1. Get PR files
        pr_files = await self.github.get_pr_files(...)

        # 2. Filter testable files
        testable_files = [f for f in pr_files if self._is_testable(...)]

        # 3. Generate tests via LLM
        response = await self.llm.ainvoke(GENERATE_TESTS_PROMPT.format(...))

        # 4. Return formatted response
        return TESTS_SUCCESS.format(...)
```

---

## 🔜 Future Enhancements

Những cải tiến có thể thêm sau:

| Enhancement              | Description                         | Priority  |
| ------------------------ | ----------------------------------- | --------- |
| **Auto-commit tests**    | Option to commit test file directly | 🟡 Medium |
| **Coverage integration** | Show coverage impact                | 🟡 Medium |
| **Multi-language**       | JavaScript/TypeScript support       | 🟢 Low    |
| **Mutation testing**     | Validate test effectiveness         | 🟢 Low    |

### Detailed Enhancement Ideas

#### 1. Auto-commit Tests

```markdown
@reviewer tests --commit

Bot: Created `tests/test_auth.py` with 5 test cases.
View commit: abc1234
```

#### 2. Coverage Integration

```markdown
## 📊 Test Coverage Impact

| File    | Before | After | Change  |
| ------- | ------ | ----- | ------- |
| auth.py | 45%    | 82%   | +37% ⬆️ |
```

#### 3. Mutation Testing

```markdown
## 🧬 Mutation Testing Results

| Mutant            | Status      |
| ----------------- | ----------- |
| Remove null check | 🔴 Killed   |
| Change < to <=    | 🔴 Killed   |
| Remove exception  | ⚠️ Survived |
```

---

## 📚 Original Design Reference

Xem design ban đầu (đã implement một phần):

### Graph Integration (Not yet implemented)

```python
# Potential future: Auto-generate tests in review pipeline

g.add_node("generate_tests", test_generator.run)
g.add_edge("extract", "generate_tests")
g.add_edge("generate_tests", "publish_tests")
```

### Test Publisher (Not yet implemented)

```python
# Potential future: Commit tests directly

await github.create_file_in_pr(
    path="tests/test_auth.py",
    content=test_content,
    message="🧪 Add AI-generated tests",
)
```

---

## 🔗 Related

- Current implementation: `src/chat/handler.py`
- Prompt template: `src/chat/prompts.py` → `GENERATE_TESTS_PROMPT`
