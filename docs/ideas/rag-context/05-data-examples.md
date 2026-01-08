# 05. Data Examples - AST & Vector DB

Tài liệu này giải thích cụ thể data được lưu trữ và xử lý như thế nào.

---

## 🌳 AST (Tree-sitter) - Parse ra được gì?

### Input: File Python

```python
# src/services/order.py
from models import Order, Item
from utils.pricing import apply_discount

class OrderService:
    """Service for handling orders."""

    def __init__(self, db):
        self.db = db

    def calculate_total(self, items: list[Item], discount: float = 0) -> float:
        """Calculate total price with discount."""
        subtotal = sum(item.price * item.quantity for item in items)
        return apply_discount(subtotal, discount)

    def create_order(self, user_id: int, items: list[Item]) -> Order:
        """Create a new order."""
        total = self.calculate_total(items)
        order = Order(user_id=user_id, total=total)
        return self.db.save(order)
```

### Output: List of CodeChunks

```python
[
    CodeChunk(
        chunk_type="class",
        name="OrderService",
        signature=None,
        content="class OrderService:\n    \"\"\"Service for handling orders.\"\"\"...",
        file_path="src/services/order.py",
        start_line=5,
        end_line=21,
        language="python",
        docstring="Service for handling orders.",
    ),
    CodeChunk(
        chunk_type="method",
        name="calculate_total",
        signature="def calculate_total(self, items: list[Item], discount: float = 0) -> float:",
        content="def calculate_total(self, items: list[Item], discount: float = 0) -> float:\n    \"\"\"Calculate total price with discount.\"\"\"...",
        file_path="src/services/order.py",
        start_line=11,
        end_line=14,
        language="python",
        docstring="Calculate total price with discount.",
    ),
    CodeChunk(
        chunk_type="method",
        name="create_order",
        signature="def create_order(self, user_id: int, items: list[Item]) -> Order:",
        content="def create_order(self, user_id: int, items: list[Item]) -> Order:\n    ...",
        file_path="src/services/order.py",
        start_line=16,
        end_line=20,
        language="python",
        docstring="Create a new order.",
    ),
]
```

### Tại sao cần AST?

| Không có AST                    | Có AST                                    |
| ------------------------------- | ----------------------------------------- |
| Chia code random (mỗi 50 lines) | Chia theo semantic unit (function, class) |
| Không biết tên function         | Biết `calculate_total` với params gì      |
| Không biết signature            | Biết `items: list[Item], discount: float` |
| Tìm kiếm kém chính xác          | Tìm kiếm chính xác theo function name     |

---

## 🗄️ Vector Database (Pinecone) - Chứa gì?

### Cấu trúc Index

```
Pinecone Index: "code-reviewer"
│
├── Namespace: "acme-corp/backend-api"
│   ├── Vector 1: src/services/order.py:calculate_total
│   ├── Vector 2: src/services/order.py:create_order
│   ├── Vector 3: tests/test_order.py:test_calculate_total
│   └── ... (hundreds more)
│
├── Namespace: "acme-corp/frontend-app"
│   └── ... (vectors for this repo)
│
└── Namespace: "other-org/other-repo"
    └── ...
```

### Chi tiết 1 Vector

```python
{
    # Unique identifier
    "id": "src/services/order.py:calculate_total:11",

    # Vector embedding (1024 floats)
    # Được tạo từ OpenAI text-embedding-3-small
    "values": [0.023, -0.145, 0.872, 0.031, ..., 0.421],  # 1024 dimensions

    # Metadata (để filter và display)
    "metadata": {
        "file_path": "src/services/order.py",
        "name": "calculate_total",
        "chunk_type": "method",
        "language": "python",
        "start_line": 11,
        "end_line": 14,
        # Content truncated để tiết kiệm space
        "content": "def calculate_total(self, items: list[Item], discount: float = 0) -> float:\n    \"\"\"Calculate total price with discount.\"\"\"\n    subtotal = sum(item.price * item.quantity for item in items)\n    return apply_discount(subtotal, discount)"
    }
}
```

### Embedding được tạo từ gì?

```python
# Text được gửi đến OpenAI để embed:
embedding_text = """
method: calculate_total
Signature: def calculate_total(self, items: list[Item], discount: float = 0) -> float:
Docstring: Calculate total price with discount.
Code:
def calculate_total(self, items: list[Item], discount: float = 0) -> float:
    subtotal = sum(item.price * item.quantity for item in items)
    return apply_discount(subtotal, discount)
"""

# OpenAI trả về vector 1024 dimensions
embedding = openai.embed(embedding_text, dimensions=1024)
# → [0.023, -0.145, 0.872, ..., 0.421]
```

---

## 🔍 Query Pinecone - Hoạt động như nào?

### Scenario: Đang review PR sửa `calculate_total`

**Step 1: Tạo query từ code đang review**

```python
query_text = """
method: calculate_total
Signature: def calculate_total(self, items: list[Item], discount: float = 0) -> float
Context: order pricing calculation with discount
"""
```

**Step 2: Embed query**

```python
query_vector = openai.embed(query_text, dimensions=1024)
# → [0.025, -0.140, 0.865, ..., 0.415]
```

**Step 3: Search Pinecone**

```python
results = pinecone.query(
    namespace="acme-corp/backend-api",
    vector=query_vector,
    top_k=5,
    filter={"file_path": {"$ne": "src/services/order.py"}},  # Exclude self
    include_metadata=True
)
```

**Step 4: Kết quả (sorted by similarity)**

```python
[
    {
        "id": "tests/test_order.py:test_calculate_total:5",
        "score": 0.92,  # Rất similar! Đây là test
        "metadata": {
            "file_path": "tests/test_order.py",
            "name": "test_calculate_total",
            "content": "def test_calculate_total():\n    service = OrderService(mock_db)..."
        }
    },
    {
        "id": "src/api/checkout.py:process_checkout:20",
        "score": 0.85,  # Similar - gọi calculate_total
        "metadata": {
            "file_path": "src/api/checkout.py",
            "name": "process_checkout",
            "content": "def process_checkout(...):\n    total = order_service.calculate_total(items, discount)..."
        }
    },
    {
        "id": "src/services/cart.py:compute_cart_total:15",
        "score": 0.78,  # Similar pattern
        "metadata": {
            "file_path": "src/services/cart.py",
            "name": "compute_cart_total",
            "content": "def compute_cart_total(cart):\n    return sum(item.price * item.qty for item in cart.items)"
        }
    }
]
```

---

## 🔄 Clone vs API - Khi nào dùng cái nào?

### Điểm quan trọng cần nhớ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  INITIAL INDEXING (installation.created)                                    │
│  ══════════════════════════════════════                                     │
│                                                                              │
│  • Cần đọc TẤT CẢ files (có thể 1000+ files)                               │
│  • Dùng GitHub API: 1000 files = 1000 API calls = CHẬM + Rate limit        │
│  • → CLONE REPO (1 command = tất cả files)                                 │
│  • → Xong thì XÓA (không giữ lại)                                          │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  INCREMENTAL UPDATE (pull_request.closed + merged)                          │
│  ═════════════════════════════════════════════════                          │
│                                                                              │
│  • Chỉ cần update VÀI files thay đổi trong PR (5-20 files)                 │
│  • Dùng GitHub API: 20 files = 20 API calls = OK!                          │
│  • → KHÔNG CẦN CLONE                                                       │
│  • → Dùng API lấy từng file                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### So sánh

|                 | Initial Indexing      | Incremental Update  |
| --------------- | --------------------- | ------------------- |
| **Trigger**     | App installed         | PR merged           |
| **Files**       | ALL (~1000)           | Changed only (~10)  |
| **Method**      | `git clone --depth 1` | GitHub API per file |
| **Clone repo?** | ✅ Yes, then delete   | ❌ No               |
| **Time**        | 5-30 min              | 10-30 sec           |

### Tại sao không giữ repo clone sẵn?

```
❌ Giữ clone sẵn:
• 1000 repos × 100MB = 100GB disk
• Phải git pull mỗi khi update
• Quản lý disk space phức tạp

✅ Clone khi cần, xóa khi xong:
• Không tốn disk
• Incremental dùng API (chỉ vài files)
• Simpler architecture
```

---

## 📊 Data Size Estimates

| Repo Size | Files | Chunks | Vectors | Pinecone Storage |
| --------- | ----- | ------ | ------- | ---------------- |
| 10K LOC   | 100   | 300    | 300     | ~1MB             |
| 100K LOC  | 1000  | 3000   | 3000    | ~10MB            |
| 1M LOC    | 10000 | 30000  | 30000   | ~100MB           |

**Pinecone Free Tier**: 100K vectors → Đủ cho ~30 repos medium size

---

## ✅ Summary

1. **AST Parser**: Chia code thành semantic units (function, class) với metadata
2. **Vector DB**: Lưu embeddings của mỗi chunk + metadata để search
3. **Query**: Embed query text → Search similar vectors → Return related code
4. **Clone**: Chỉ dùng cho initial indexing, không dùng cho updates
