# 02. Tree-sitter Integration

## 🌳 Tree-sitter là gì?

Tree-sitter là một parser generator cho phép parse source code thành **Abstract Syntax Tree (AST)** - cấu trúc dữ liệu biểu diễn code theo dạng cây.

```
Source Code (text)  ──▶  AST (structured tree)  ──▶  Semantic Information
```

### Ví dụ đơn giản

```python
# Source code
def add(a, b):
    return a + b
```

```
# AST representation
FunctionDefinition
├── name: "add"
├── parameters: ["a", "b"]
├── body:
│   └── ReturnStatement
│       └── BinaryExpression
│           ├── left: "a"
│           ├── operator: "+"
│           └── right: "b"
```

---

## 🤔 Tại sao cần Tree-sitter?

### So sánh các approaches

| Approach              | Cách làm              | Ưu điểm            | Nhược điểm                       |
| --------------------- | --------------------- | ------------------ | -------------------------------- |
| **Regex**             | Pattern matching text | Đơn giản           | Thiếu chính xác, miss edge cases |
| **Language-specific** | Python's `ast` module | Chính xác          | Chỉ 1 ngôn ngữ                   |
| **Tree-sitter**       | Universal parser      | Đa ngôn ngữ, nhanh | Cần setup                        |

### Trong context review code

```
Không có Tree-sitter:
├── Agent thấy: "+ def calculate_total(items, discount=0):"
├── Hiểu: "Có dòng code bắt đầu bằng def"
└── Không biết: Đây là function? Class? Có params gì? Return gì?

Có Tree-sitter:
├── Agent biết: "Đây là function definition"
├── Name: calculate_total
├── Parameters: items (required), discount (optional, default=0)
├── Nằm trong class: OrderService (nếu có)
└── Gọi các functions khác: sum(), item.price
```

---

## 📊 Tree-sitter extract được gì?

### 1. Symbols (Functions, Classes, Variables)

```
┌────────────────────────────────────────────────────────┐
│  Từ file source code, Tree-sitter extract:             │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Functions:                                            │
│  ┌──────────────────────────────────────────────────┐ │
│  │ name: "calculate_total"                          │ │
│  │ type: function                                   │ │
│  │ line_start: 10                                   │ │
│  │ line_end: 15                                     │ │
│  │ signature: "def calculate_total(items, discount)"│ │
│  │ parent: "OrderService" (nếu là method)           │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Classes:                                              │
│  ┌──────────────────────────────────────────────────┐ │
│  │ name: "OrderService"                             │ │
│  │ type: class                                      │ │
│  │ line_start: 5                                    │ │
│  │ line_end: 50                                     │ │
│  │ base_classes: ["BaseService"]                    │ │
│  │ methods: ["__init__", "calculate_total", ...]    │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 2. Function Calls (ai gọi ai)

```
┌────────────────────────────────────────────────────────┐
│  Function calls trong file:                            │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Line 12: self.db.get_order(order_id)                 │
│  ┌──────────────────────────────────────────────────┐ │
│  │ receiver: "self.db"                              │ │
│  │ method: "get_order"                              │ │
│  │ arguments: ["order_id"]                          │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Line 15: sum(item.price for item in items)           │
│  ┌──────────────────────────────────────────────────┐ │
│  │ function: "sum"                                  │ │
│  │ arguments: [generator expression]                │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 3. Imports (dependencies)

```
┌────────────────────────────────────────────────────────┐
│  Imports trong file:                                   │
├────────────────────────────────────────────────────────┤
│                                                        │
│  from services.order import OrderService               │
│  ┌──────────────────────────────────────────────────┐ │
│  │ module: "services.order"                         │ │
│  │ imports: ["OrderService"]                        │ │
│  │ type: from-import                                │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  import logging                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ module: "logging"                                │ │
│  │ type: direct-import                              │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 🔄 Flow trong PR Review

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TREE-SITTER TRONG REVIEW FLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                                                        │
│  │   PR Webhook    │                                                        │
│  │   (changed:     │                                                        │
│  │   order.py)     │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 1: Fetch full file content                            │           │
│  │                                                              │           │
│  │  Cần full file (không chỉ diff) để parse AST               │           │
│  │  → Call GitHub API: GET /repos/.../contents/order.py        │           │
│  └─────────────────────────────────────────────────────────────┘           │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 2: Parse với Tree-sitter                               │           │
│  │                                                              │           │
│  │  Source code ──▶ Tree-sitter ──▶ AST Tree                   │           │
│  └─────────────────────────────────────────────────────────────┘           │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 3: Extract semantic info                               │           │
│  │                                                              │           │
│  │  Từ AST, extract:                                           │           │
│  │    • Functions: tên, params, return type                    │           │
│  │    • Classes: tên, methods, base classes                    │           │
│  │    • Imports: modules, specific imports                     │           │
│  │    • Function calls: ai gọi ai                              │           │
│  └─────────────────────────────────────────────────────────────┘           │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 4: Map diff lines → AST nodes                          │           │
│  │                                                              │           │
│  │  Diff thay đổi lines 10-15                                  │           │
│  │  → Tìm: Lines 10-15 nằm trong function "calculate_total"    │           │
│  │  → Kết luận: Changed function = "calculate_total"           │           │
│  └─────────────────────────────────────────────────────────────┘           │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 5: Build enhanced context                              │           │
│  │                                                              │           │
│  │  EnhancedFileChange = {                                     │           │
│  │    patch: "... diff ...",                                   │           │
│  │    ast_info: {                                              │           │
│  │      changed_functions: ["calculate_total"],                │           │
│  │      signatures: {...},                                     │           │
│  │      imports: [...],                                        │           │
│  │      calls_in_changed_code: [...]                           │           │
│  │    }                                                        │           │
│  │  }                                                          │           │
│  └─────────────────────────────────────────────────────────────┘           │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │  STEP 6: Send to agents với rich context                    │           │
│  │                                                              │           │
│  │  Logic agent nhận:                                          │           │
│  │    • Diff (như cũ)                                          │           │
│  │    • + AST info về changed functions                        │           │
│  │    • + Function signatures                                  │           │
│  │    • + Internal dependencies                                │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Specific Use Cases

### Use Case 1: Detect function signature changes

```
Diff:
- def calculate_total(items):
+ def calculate_total(items, discount=0):

Tree-sitter phát hiện:
┌────────────────────────────────────────────────────────┐
│ Signature Change Detected                              │
├────────────────────────────────────────────────────────┤
│ Function: calculate_total                              │
│ Old params: [items]                                    │
│ New params: [items, discount]                          │
│ Added: discount (optional, default=0)                  │
│ Breaking change: NO (có default value)                 │
└────────────────────────────────────────────────────────┘
```

### Use Case 2: Detect scope của change

```
Diff shows changes at lines 45-50

Tree-sitter analysis:
┌────────────────────────────────────────────────────────┐
│ Change Location                                        │
├────────────────────────────────────────────────────────┤
│ Lines 45-50 are inside:                                │
│   • Method: process_order                              │
│   • Class: OrderService                                │
│   • File: services/order.py                            │
│                                                        │
│ The method process_order:                              │
│   • Has 3 parameters: self, order_id, options          │
│   • Returns: Order                                     │
│   • Calls: db.get_order, calculate_total, log.info    │
└────────────────────────────────────────────────────────┘
```

### Use Case 3: Understand dependencies

```
File being reviewed imports:
┌────────────────────────────────────────────────────────┐
│ Dependencies                                           │
├────────────────────────────────────────────────────────┤
│ from models import Order, Item                         │
│ from services.payment import PaymentService            │
│ from utils.pricing import apply_discount               │
│                                                        │
│ → AI biết context: file này dùng Order, Item models   │
│ → AI biết: có thể liên quan đến payment, pricing      │
└────────────────────────────────────────────────────────┘
```

---

## 📦 Data Models (Concepts)

### FileAST - Output chính của Tree-sitter

```
FileAST
├── file_path: đường dẫn file
├── language: python/javascript/...
│
├── symbols: danh sách tất cả symbols
│   ├── functions
│   ├── classes
│   ├── variables
│   └── constants
│
├── imports: danh sách imports
│   ├── module name
│   ├── imported names
│   └── aliases
│
├── function_calls: danh sách lời gọi hàm
│   ├── function name
│   ├── receiver (nếu method call)
│   └── arguments
│
└── Helper methods:
    ├── get_symbol_at_line(line) → Symbol
    ├── get_functions() → list[Symbol]
    └── get_calls_in_range(start, end) → list[FunctionCall]
```

---

## 🌐 Multi-language Support

### Supported Languages

| Language                  | Priority | Notes                        |
| ------------------------- | -------- | ---------------------------- |
| **Python**                | High     | Primary language của project |
| **JavaScript/TypeScript** | Medium   | Common in web projects       |
| **PHP**                   | Medium   | Cho các project PHP          |
| **Go**                    | Low      | Later                        |
| **Java**                  | Low      | Later                        |

### Language Detection

```
File extension → Language:
├── .py → Python
├── .js, .jsx → JavaScript
├── .ts, .tsx → TypeScript
├── .php → PHP
└── Others → Skip (no AST, use diff only)
```

---

## 💡 Key Benefits Summary

| Benefit                  | Description                           |
| ------------------------ | ------------------------------------- |
| **Understand structure** | Biết đâu là function, class, variable |
| **Know boundaries**      | Biết function bắt đầu/kết thúc ở đâu  |
| **Parse signatures**     | Biết params, types, return values     |
| **Track calls**          | Biết function nào gọi function nào    |
| **Rich metadata**        | Docstrings, decorators, visibility    |
| **Accurate chunking**    | Chunk code theo semantic units        |

---

## 🔗 Kết hợp với RAG

Tree-sitter giúp RAG hoạt động tốt hơn:

```
┌──────────────────────────────────────────────────────────────────┐
│  TREE-SITTER → RAG SYNERGY                                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. Better Chunking                                               │
│     Tree-sitter: "Đây là function calculate_total, lines 10-25"  │
│     → RAG chunk = exactly that function                          │
│     (thay vì chia đều 50 lines/chunk)                            │
│                                                                   │
│  2. Better Query                                                  │
│     Tree-sitter: "Changed function: calculate_total"             │
│     → RAG query = "calculate_total function"                     │
│     (thay vì query cả diff text)                                 │
│                                                                   │
│  3. Richer Metadata                                               │
│     Tree-sitter: signature, params, docstring                    │
│     → Stored with RAG chunks for better search                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔜 Next Steps

Xem [03-rag-system.md](./03-rag-system.md) để hiểu RAG system hoạt động thế nào.
