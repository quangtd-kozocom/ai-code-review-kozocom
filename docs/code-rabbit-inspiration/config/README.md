# Configuration System - Implementation Guide

> **Feature**: Repository Configuration System  
> **Priority**: 🔴 Critical  
> **Effort**: 3 days

---

## 📂 Documentation Structure

| File                                                           | Purpose                         | Read Order |
| -------------------------------------------------------------- | ------------------------------- | ---------- |
| [01-overview.md](./01-overview.md)                             | What & Why                      | 1st        |
| [02-architecture.md](./02-architecture.md)                     | System design & tech stack      | 2nd        |
| [03-database-schema.md](./03-database-schema.md)               | PostgreSQL tables               | 3rd        |
| [04-pydantic-models.md](./04-pydantic-models.md)               | Python models                   | 4th        |
| [05-config-service.md](./05-config-service.md)                 | Core service implementation     | 5th        |
| [06-agent-integration.md](./06-agent-integration.md)           | How to use in agents            | 6th        |
| [07-testing-guide.md](./07-testing-guide.md)                   | Testing checklist               | 7th        |
| [08-environment-setup.md](./08-environment-setup.md)           | Neon, Upstash, dependencies     | 8th        |
| [09-professional-libraries.md](./09-professional-libraries.md) | SQLModel, Redis-OM, DI patterns | 9th ⭐     |

---

## 🎯 Quick Summary

```
User commits .reviewer.yaml → Webhook triggers → Config loaded →
Stored in PostgreSQL → Cached in Redis → Applied to agents
```

---

## ✅ Definition of Done

- [ ] Config loads from `.reviewer.yaml` in repo
- [ ] Fallback to database config if no file
- [ ] Fallback to defaults if nothing exists
- [ ] Redis caching with 5-min TTL
- [ ] Path instructions applied to agent prompts
- [ ] Ignore patterns filter files
- [ ] Profile affects review strictness
- [ ] Unit tests pass
- [ ] Integration test with real config
