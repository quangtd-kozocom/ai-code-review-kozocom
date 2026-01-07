# RAG Context v2

## Goal

Provide **explicit, quality context** to LLM during code review.

## Problem with v1

- Uses semantic similarity → returns "similar" code that isn't actually related
- LLM receives noise instead of useful context

## Solution

Only retrieve code with **explicit relationships**:

| Type   | How Found                | Value                |
| ------ | ------------------------ | -------------------- |
| TEST   | Pattern match test file  | Expected behavior    |
| CALLER | Query `calls` metadata   | How function is used |
| CALLEE | Query function's `calls` | Dependencies         |

**No fallback to "similar" code.**

## Architecture

Plugin system for multi-language support:

```
src/languages/
├── base.py        # Interface: parse_imports, parse_calls, get_test_patterns
├── python.py      # Python implementation
├── javascript.py  # JS/TS implementation
└── php.py         # PHP implementation
```

## Implementation

See [implementation-plan.md](./implementation-plan.md) for step-by-step guide.

## Status

- [ ] Language plugin system
- [ ] Python plugin
- [ ] JavaScript/TypeScript plugin
- [ ] PHP plugin
- [ ] AST parser refactor
- [ ] RAG retriever refactor
- [ ] Testing
