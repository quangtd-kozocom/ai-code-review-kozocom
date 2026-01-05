# 📋 Configuration System - Overview

> **Priority**: 🔴 Critical  
> **Estimated Effort**: 3-4 days  
> **Dependencies**: None (foundation feature)

---

## 🎯 Mục Tiêu

Cho phép users **customize AI reviewer behavior** thông qua file `.reviewer.yaml` trong repository của họ.

---

## ❓ Tại Sao Cần Feature Này?

### Problem Statement

Hiện tại, mọi thứ đều **hardcoded**:

- Confidence threshold: 0.7 (cố định)
- Max comments per file: 10 (cố định)
- Agents chạy: security, logic, style (cố định)
- Không thể ignore files/folders
- Không có path-specific instructions

### Impact

| Vấn đề                          | Hậu quả                          |
| ------------------------------- | -------------------------------- |
| Không ignore được `migrations/` | Noise từ auto-generated files    |
| Cùng rules cho mọi file         | False positives cao ở test files |
| Không customize được            | Mỗi team có standards khác nhau  |

---

## ✅ Giải Pháp

Tạo hệ thống configuration với file `.reviewer.yaml`:

```yaml
# .reviewer.yaml trong root của repository
language: "vi"

reviews:
  profile: "chill"
  confidence_threshold: 0.7

  path_instructions:
    - path: "src/api/**"
      instructions: "Check authentication"

  auto_review:
    enabled: true
    drafts: false

ignore:
  paths:
    - "**/migrations/**"
    - "**/__pycache__/**"
```

---

## 📊 So Sánh với CodeRabbit

| Feature                   | CodeRabbit            | Chúng ta (Phase 1)        |
| ------------------------- | --------------------- | ------------------------- |
| YAML config file          | ✅ `.coderabbit.yaml` | ✅ `.reviewer.yaml`       |
| Review profiles           | ✅ chill/assertive    | ✅ chill/assertive/strict |
| Path instructions         | ✅                    | ✅                        |
| Ignore patterns           | ✅                    | ✅                        |
| Auto review settings      | ✅                    | ✅                        |
| Central config (org-wide) | ✅                    | ❌ Phase 2                |
| Web UI config             | ✅                    | ❌ Out of scope           |

---

## 🗂️ Documents Liên Quan

| File                                                       | Nội dung                       |
| ---------------------------------------------------------- | ------------------------------ |
| [02-coderabbit-reference.md](./02-coderabbit-reference.md) | Chi tiết config của CodeRabbit |
| [03-our-config-schema.md](./03-our-config-schema.md)       | Schema config cho project      |
| [04-implementation-plan.md](./04-implementation-plan.md)   | Kế hoạch implement             |
| [05-example-configs.md](./05-example-configs.md)           | Ví dụ config files             |

---

## ⏳ Timeline

```
Day 1: Pydantic models + basic loader
Day 2: Agent integration + path matching
Day 3: Testing + documentation
Day 4: Buffer / refinement
```
