# 04. Combined Flow: RAG + Tree-sitter

## 🎯 The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   Tree-sitter = MICROSCOPE 🔬          RAG = TELESCOPE 🔭                   │
│   Nhìn SÂU vào file đang review       Nhìn RỘNG ra toàn codebase           │
│                                                                              │
│   • Hiểu structure                     • Tìm related code                   │
│   • Parse types, params                • Tìm callers/usages                 │
│   • Detect function scope              • Tìm tests                          │
│   • Understand data flow               • Detect patterns                    │
│                                                                              │
│                         ┌─────────────┐                                      │
│                         │   COMBINE   │                                      │
│                         │      =      │                                      │
│                         │ FULL VIEW   │                                      │
│                         └─────────────┘                                      │
│                                                                              │
│   AI có đầy đủ context để review chính xác hơn                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Review Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE PR REVIEW FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  1. GITHUB WEBHOOK                                                   │   │
│   │     PR opened/updated on repository                                  │   │
│   └─────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  2. ACKNOWLEDGE                                                      │   │
│   │     Post comment: "🤖 Đang review..."                                │   │
│   └─────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  3. CONTEXT EXTRACTION (ENHANCED)     ◀═══ CORE CHANGES HERE        │   │
│   │                                                                      │   │
│   │     ┌─────────────────────────────────────────────────────────────┐ │   │
│   │     │  3a. Fetch PR data (như cũ)                                 │ │   │
│   │     │      - List of changed files                                │ │   │
│   │     │      - Diff/patch for each file                             │ │   │
│   │     └─────────────────────────────────────────────────────────────┘ │   │
│   │                              │                                       │   │
│   │                              ▼                                       │   │
│   │     ┌─────────────────────────────────────────────────────────────┐ │   │
│   │     │  3b. Fetch full file content (NEW)                          │ │   │
│   │     │      - Need full file for Tree-sitter parsing               │ │   │
│   │     │      - Fetch từ GitHub API                                  │ │   │
│   │     └─────────────────────────────────────────────────────────────┘ │   │
│   │                              │                                       │   │
│   │     ┌────────────────────────┴────────────────────────┐             │   │
│   │     │                                                  │             │   │
│   │     ▼                                                  ▼             │   │
│   │  ┌──────────────────────────┐    ┌──────────────────────────┐       │   │
│   │  │  3c. TREE-SITTER         │    │  3d. RAG RETRIEVAL       │       │   │
│   │  │                          │    │                          │       │   │
│   │  │  • Parse full file       │    │  • Query vector DB       │       │   │
│   │  │  • Extract:              │    │  • Find:                 │       │   │
│   │  │    - Functions           │    │    - Similar code        │       │   │
│   │  │    - Classes             │    │    - Callers             │       │   │
│   │  │    - Imports             │    │    - Related tests       │       │   │
│   │  │    - Function calls      │    │    - Documentation       │       │   │
│   │  │  • Map diff → AST nodes  │    │                          │       │   │
│   │  │  • Identify changed      │    │  Input: function names   │       │   │
│   │  │    functions             │    │         from Tree-sitter │       │   │
│   │  │                          │    │                          │       │   │
│   │  └────────────┬─────────────┘    └────────────┬─────────────┘       │   │
│   │               │                               │                      │   │
│   │               └───────────────┬───────────────┘                      │   │
│   │                               │                                      │   │
│   │                               ▼                                      │   │
│   │     ┌─────────────────────────────────────────────────────────────┐ │   │
│   │     │  3e. BUILD ENHANCED FILE CHANGE                             │ │   │
│   │     │                                                             │ │   │
│   │     │  EnhancedFileChange {                                       │ │   │
│   │     │    filename: "services/order.py"                            │ │   │
│   │     │    patch: "... git diff ..."           ◀── Như cũ           │ │   │
│   │     │                                                             │ │   │
│   │     │    ast_info: {                         ◀── From Tree-sitter │ │   │
│   │     │      changed_functions: ["calculate_total"]                 │ │   │
│   │     │      function_signatures: {...}                             │ │   │
│   │     │      imports: [...]                                         │ │   │
│   │     │    }                                                        │ │   │
│   │     │                                                             │ │   │
│   │     │    related_context: {                  ◀── From RAG         │ │   │
│   │     │      callers: ["OrderService.process_order"]                │ │   │
│   │     │      similar_code: [...]                                    │ │   │
│   │     │      tests: ["test_calculate_total"]                        │ │   │
│   │     │    }                                                        │ │   │
│   │     │  }                                                          │ │   │
│   │     └─────────────────────────────────────────────────────────────┘ │   │
│   │                                                                      │   │
│   └─────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  4. PARALLEL AGENTS (với enhanced context)                           │   │
│   │                                                                      │   │
│   │     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │   │
│   │     │   SECURITY   │  │    LOGIC     │  │    STYLE     │            │   │
│   │     │    AGENT     │  │    AGENT     │  │    AGENT     │            │   │
│   │     │              │  │              │  │              │            │   │
│   │     │  Receives:   │  │  Receives:   │  │  Receives:   │            │   │
│   │     │  • Diff      │  │  • Diff      │  │  • Diff      │            │   │
│   │     │  • AST info  │  │  • AST info  │  │  • AST info  │            │   │
│   │     │  • Context   │  │  • Context   │  │  • Patterns  │            │   │
│   │     │              │  │  • Callers   │  │              │            │   │
│   │     └──────────────┘  └──────────────┘  └──────────────┘            │   │
│   │                                                                      │   │
│   └─────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  5. AGGREGATE → 6. PUBLISH → 7. NOTIFY                               │   │
│   │     (như cũ)                                                         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Ví dụ cụ thể

### Scenario: PR thay đổi function `calculate_total`

**PR Diff:**

```python
# services/order.py
- def calculate_total(items):
-     return sum(item.price for item in items)
+ def calculate_total(items, discount=0):
+     total = sum(item.price for item in items)
+     return total * (1 - discount)
```

### Step by step flow:

````
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Tree-sitter phân tích                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Parse full file → Extract:                                                  │
│                                                                              │
│  changed_functions: [{                                                       │
│    name: "calculate_total",                                                  │
│    old_signature: "calculate_total(items)",                                  │
│    new_signature: "calculate_total(items, discount=0)",                      │
│    changes: ["added parameter: discount (default=0)"],                       │
│    return_type: "float",                                                     │
│  }]                                                                          │
│                                                                              │
│  observations:                                                               │
│    - Parameter added with default value → backward compatible ✓             │
│    - New calculation: total * (1 - discount)                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: RAG tìm related code                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Query: "calculate_total function order pricing"                             │
│                                                                              │
│  Results:                                                                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. CALLERS (ai gọi function này)                                   │    │
│  │     • OrderService.process_order() - line 45                        │    │
│  │       "total = calculate_total(order.items)"                        │    │
│  │     • CheckoutAPI.complete() - line 78                              │    │
│  │       "order.total = calculate_total(items)"                        │    │
│  │                                                                      │    │
│  │  2. RELATED TESTS                                                   │    │
│  │     • test_order.py::test_calculate_total                           │    │
│  │     • test_order.py::test_calculate_total_empty                     │    │
│  │       (Chú ý: chưa có test cho discount!)                           │    │
│  │                                                                      │    │
│  │  3. SIMILAR CODE                                                    │    │
│  │     • CartService.get_subtotal() - similar pattern                  │    │
│  │       "return sum(item.price for item in self.items)"               │    │
│  │                                                                      │    │
│  │  4. DOCUMENTATION                                                   │    │
│  │     • docs/pricing.md mentions calculate_total                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Agent nhận FULL CONTEXT                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Logic Agent Prompt:                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ## Code Changes                                                     │    │
│  │  ```diff                                                             │    │
│  │  - def calculate_total(items):                                      │    │
│  │  + def calculate_total(items, discount=0):                          │    │
│  │  ```                                                                 │    │
│  │                                                                      │    │
│  │  ## AST Analysis (Tree-sitter)                                       │    │
│  │  - Function: calculate_total                                         │    │
│  │  - Parameter added: discount (float, default=0)                      │    │
│  │  - Backward compatible: YES (có default value)                       │    │
│  │                                                                      │    │
│  │  ## Codebase Context (RAG)                                           │    │
│  │  This function is called by:                                         │    │
│  │  - OrderService.process_order() [không pass discount]               │    │
│  │  - CheckoutAPI.complete() [không pass discount]                      │    │
│  │                                                                      │    │
│  │  Existing tests:                                                     │    │
│  │  - test_calculate_total ✓                                           │    │
│  │  - test_calculate_total_empty ✓                                     │    │
│  │  - test_calculate_total_with_discount ❌ (chưa có)                  │    │
│  │                                                                      │    │
│  │  ## Your Analysis                                                    │    │
│  │  Review the changes considering the context above...                 │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Agent output (SMARTER với context)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ✅ GOOD: Parameter có default value nên backward compatible        │    │
│  │                                                                      │    │
│  │  ⚠️ WARNING: Discount validation                                    │    │
│  │     Line 3: Nên validate discount (0 <= discount <= 1)              │    │
│  │     Suggestion: "if not 0 <= discount <= 1: raise ValueError(...)" │    │
│  │                                                                      │    │
│  │  💡 SUGGESTION: Missing test coverage                                │    │
│  │     Existing tests don't cover discount parameter.                   │    │
│  │     Consider adding: test_calculate_total_with_discount              │    │
│  │                                                                      │    │
│  │  📝 INFO: Callers không bị break                                    │    │
│  │     OrderService.process_order() và CheckoutAPI.complete()          │    │
│  │     không cần update vì discount có default value.                   │    │
│  │     Nhưng có thể muốn update để sử dụng discount feature.           │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
````

---

## 🆚 So sánh: Có vs Không có RAG + Tree-sitter

| Aspect              | Không có              | Có                                           |
| ------------------- | --------------------- | -------------------------------------------- |
| **Input cho AI**    | Chỉ diff text         | Diff + AST + Related code                    |
| **Hiểu function**   | "Có thêm param gì đó" | "Thêm discount param, có default value"      |
| **Biết callers**    | ❌ Không              | ✅ Biết 2 chỗ gọi function này               |
| **Biết tests**      | ❌ Không              | ✅ Biết có 2 tests nhưng chưa cover discount |
| **Suggestions**     | Generic               | Specific với context                         |
| **False positives** | Cao (~30%)            | Thấp (<15%)                                  |

---

## 🔑 Key Benefits

### 1. Smarter Suggestions

```
Before: "Consider validating input"
After:  "Validate discount: 0 <= discount <= 1,
         vì callers có thể pass invalid values"
```

### 2. Cross-file Awareness

```
Before: Không biết ai dùng function này
After:  "2 callers không pass discount,
         nhưng backward compatible vì có default"
```

### 3. Test Coverage Insights

```
Before: Không mention tests
After:  "Missing test for discount case.
         Add: test_calculate_total_with_discount"
```

### 4. Pattern Detection

```
Before: Review từng file độc lập
After:  "CartService.get_subtotal() có similar pattern,
         consider extracting to shared utility"
```

---

## 📊 Data Flow Summary

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   GitHub     │     │  Tree-sitter │     │     RAG      │
│   (diff)     │     │   (parse)    │     │  (retrieve)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                                                          │
│               EnhancedFileChange                         │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │   diff     │  │  ast_info  │  │  context   │        │
│  │   (text)   │  │ (structure)│  │ (related)  │        │
│  └────────────┘  └────────────┘  └────────────┘        │
│                                                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    AI Agent          │
              │    (full context)    │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Smart Review       │
              │   Comments           │
              └──────────────────────┘
```

---

## 🔜 Next Steps

Xem [05-implementation.md](./05-implementation.md) để biết thứ tự implement và dependencies.
