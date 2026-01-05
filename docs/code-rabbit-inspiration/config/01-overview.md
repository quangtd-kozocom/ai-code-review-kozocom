# 01 - Overview: Configuration System

## 🎯 What Is This?

Hệ thống cho phép mỗi repository customize AI reviewer behavior thông qua file `.reviewer.yaml`.

---

## ❓ Why Do We Need This?

### Current Problems

```
❌ Hardcoded confidence_threshold = 0.7
❌ Cannot ignore migrations/, __pycache__/
❌ Same rules for all files (tests, api, models)
❌ Cannot disable specific agents
❌ Every team forced same behavior
```

### After Implementation

```
✅ Per-repo configuration
✅ Path-specific instructions ("check auth in api/")
✅ Ignore patterns
✅ Adjustable thresholds
✅ Enable/disable agents
```

---

## 📋 Minimal Config Example

```yaml
# .reviewer.yaml
language: "vi"

reviews:
  profile: "chill"
  confidence_threshold: 0.7
  path_instructions:
    - path: "src/api/**"
      instructions: "Check authentication"

ignore:
  - "**/migrations/**"
```

---

## 🔄 Config Resolution Order

```
Priority (High → Low):
1. .reviewer.yaml in repository  ← Highest
2. Database config (per-repo)
3. Default values               ← Lowest
```

---

## 📊 Scope

### In Scope (MVP)

- [x] Load config from `.reviewer.yaml`
- [x] Store defaults in PostgreSQL
- [x] Cache in Redis
- [x] Path-based instructions
- [x] Ignore patterns
- [x] Profile selection
- [x] Auto-review settings

### Out of Scope (Future)

- [ ] Web UI for config editing
- [ ] Org-wide central config
- [ ] Config validation command
- [ ] Config history/versioning

---

## 🗂️ Files to Create/Modify

```
src/
├── core/
│   └── config/                    # NEW MODULE
│       ├── __init__.py
│       ├── models.py              # Pydantic models
│       ├── service.py             # ConfigService class
│       ├── repository.py          # Database operations
│       └── cache.py               # Redis cache
├── agents/
│   ├── state.py                   # Add repo_config field
│   └── nodes/
│       ├── context_extractor.py   # Load config
│       ├── security_agent.py      # Use config
│       ├── logic_agent.py         # Use config
│       └── style_agent.py         # Use config
└── app/
    └── services/
        └── github.py              # Add get_file_raw()
```
