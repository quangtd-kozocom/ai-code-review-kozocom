# 🔧 Configuration System

> **Priority**: 🔴 Critical  
> **Effort**: 3-4 days  
> **Status**: 📋 Planning

---

## 📂 Documentation

| File                                                             | Description                           |
| ---------------------------------------------------------------- | ------------------------------------- |
| [01-overview.md](./01-overview.md)                               | Tại sao cần feature này, goals        |
| [02-coderabbit-reference.md](./02-coderabbit-reference.md)       | Deep dive vào CodeRabbit config       |
| [03-our-config-schema.md](./03-our-config-schema.md)             | Schema đầy đủ (reference)             |
| [04-implementation-plan.md](./04-implementation-plan.md)         | Step-by-step plan với code            |
| [05-example-configs.md](./05-example-configs.md)                 | Ví dụ configs cho các use cases       |
| **[06-architecture-decision.md](./06-architecture-decision.md)** | **⭐ Simplified schema + Tech stack** |

---

## 🎯 TL;DR

**Problem**: Hiện tại mọi thứ hardcoded, không thể customize.

**Solution**: File `.reviewer.yaml` cho phép:

- Custom review profiles (chill/strict)
- Path-based instructions
- Ignore patterns
- Auto-review settings

**Quick Example**:

```yaml
# .reviewer.yaml
language: "vi"
reviews:
  profile: "chill"
  path_instructions:
    - path: "tests/**"
      instructions: "Light review only"
ignore:
  paths:
    - "**/migrations/**"
```

---

## 📊 Key Features

| Feature               | Description                                              |
| --------------------- | -------------------------------------------------------- |
| **Review Profiles**   | `chill` / `default` / `strict` - control strictness      |
| **Path Instructions** | Custom rules per directory (e.g. "check auth in api/")   |
| **Ignore Patterns**   | Skip files (`migrations/`, `__pycache__/`)               |
| **Auto Review**       | Control when to auto-review (drafts, branches, keywords) |
| **Chat Config**       | Enable/disable commands, rate limiting                   |

---

## 🔗 References

- [CodeRabbit Config Reference](https://docs.coderabbit.ai/reference/configuration)
- [CodeRabbit YAML Setup](https://docs.coderabbit.ai/getting-started/yaml-configuration)
