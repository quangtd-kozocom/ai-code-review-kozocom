# 02. Hướng Dẫn Setup và Test Thực Tế

## Mục Tiêu

Test RAG feature end-to-end với một repository thực tế.

---

## Bước 1: Chuẩn Bị API Keys

### 1.1 Lấy Pinecone API Key

1. Vào https://www.pinecone.io/
2. Đăng ký tài khoản (free tier)
3. Tạo project mới
4. Copy API Key từ dashboard

### 1.2 Đảm bảo có OpenAI API Key

Bạn cần `OPENAI_API_KEY` để tạo embeddings.

### 1.3 Thêm vào `.env`

```bash
# .env
PINECONE_API_KEY=pcsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PINECONE_INDEX_NAME=code-reviewer

# Đã có sẵn từ trước
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Bước 2: Tạo Test Repository

### 2.1 Tạo repo mới trên GitHub

Tạo repo: `your-username/rag-test-repo`

### 2.2 Thêm sample code

```bash
# Clone repo vừa tạo
git clone https://github.com/your-username/rag-test-repo
cd rag-test-repo

# Tạo structure
mkdir -p src tests
```

**File `src/calculator.py`:**

```python
"""Calculator module."""

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

def divide(a: int, b: int) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

**File `src/order.py`:**

```python
"""Order processing module."""

from dataclasses import dataclass

@dataclass
class Item:
    name: str
    price: float
    quantity: int

def calculate_total(items: list[Item], discount: float = 0) -> float:
    """Calculate total price of items with optional discount."""
    subtotal = sum(item.price * item.quantity for item in items)
    return subtotal * (1 - discount)

def apply_tax(total: float, tax_rate: float = 0.1) -> float:
    """Apply tax to total."""
    return total * (1 + tax_rate)
```

**File `tests/test_calculator.py`:**

```python
"""Tests for calculator module."""
import pytest
from src.calculator import add, subtract, multiply, divide

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(4, 3) == 12

def test_divide():
    assert divide(10, 2) == 5.0

def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)
```

**File `tests/test_order.py`:**

```python
"""Tests for order module."""
from src.order import Item, calculate_total, apply_tax

def test_calculate_total():
    items = [
        Item("Apple", 1.0, 3),
        Item("Banana", 0.5, 4),
    ]
    assert calculate_total(items) == 5.0

def test_calculate_total_with_discount():
    items = [Item("Apple", 10.0, 1)]
    assert calculate_total(items, discount=0.1) == 9.0

def test_apply_tax():
    assert apply_tax(100, 0.1) == 110.0
```

### 2.3 Push lên GitHub

```bash
git add .
git commit -m "Initial code structure"
git push origin main
```

---

## Bước 3: Cài GitHub App vào Test Repo

### 3.1 Đảm bảo GitHub App có permissions

Trong GitHub App settings (https://github.com/settings/apps/YOUR-APP):

**Repository permissions:**

| Permission    | Level            | Tại sao cần?                          |
| ------------- | ---------------- | ------------------------------------- |
| Contents      | **Read**         | Clone repo để index, đọc file content |
| Pull requests | **Read & Write** | Đọc PR files, viết review comments    |
| Issues        | **Read & Write** | Đọc/trả lời issue comments            |
| Metadata      | **Read**         | Lấy repo info (owner, name)           |

### 3.2 Subscribe to Events (QUAN TRỌNG cho RAG!)

Trong tab "Permissions & events" → "Subscribe to events":

| Event                              | Trigger                        | RAG Action                                    |
| ---------------------------------- | ------------------------------ | --------------------------------------------- |
| ✅ **Installation**                | Khi user cài App vào repo      | **Full Index** - Clone + index toàn bộ repo   |
| ✅ **Push**                        | Khi có push vào main/master    | **Incremental Update** - Update changed files |
| ✅ **Pull request**                | PR opened/reopened/synchronize | Review với RAG context                        |
| ✅ **Pull request review comment** | Comment trên review            | Chat commands (@bot fix, explain)             |
| ✅ **Issue comment**               | Comment trên PR                | Chat commands                                 |

**⚠️ Nếu thiếu events:**

```
❌ Thiếu "Installation" → Repo không được index khi cài App
❌ Thiếu "Push" → Index không update sau merge
❌ Thiếu "Pull request" → PR không được review
```

### 3.3 Webhook URL Configuration

1. Trong GitHub App settings → "Webhook"
2. **Webhook URL**: `https://YOUR-DOMAIN/api/v1/webhooks/github`
3. **Webhook secret**: Tạo secret và save vào `.env`:

```bash
# .env
GITHUB_WEBHOOK_SECRET=your-webhook-secret-here
```

4. **Content type**: `application/json`
5. **SSL verification**: Enable (nếu production)

### 3.4 Verify Webhook Delivery

Sau khi cài App, kiểm tra webhook có gửi đúng không:

1. Vào GitHub App → "Advanced" → "Recent Deliveries"
2. Tìm event `installation.created`
3. Check:
   - **Response**: `200 OK`
   - **Payload**: Có `installation.id` và `repositories`

```json
{
  "action": "created",
  "installation": {
    "id": 12345678,
    "account": { "login": "your-username" }
  },
  "repositories": [
    { "name": "rag-test-repo", "full_name": "your-username/rag-test-repo" }
  ]
}
```

### 3.5 Cài App vào repository

1. Vào GitHub App page: `https://github.com/apps/YOUR-APP-NAME`
2. Click "Install"
3. Chọn repository `rag-test-repo`
4. Confirm installation

**Expected behavior sau khi cài:**

- Webhook `installation.created` được gửi
- Server nhận và queue Celery task `index_installation`
- Repo được clone và index vào Pinecone

---

## Bước 4: Chạy Server Local

### 4.1 Terminal 1: Start FastAPI Server

```bash
cd /path/to/reviewer

# Expose local server với ngrok
ngrok http 8000
# Copy URL: https://xxxx.ngrok.io
```

Update GitHub App webhook URL: `https://xxxx.ngrok.io/api/v1/webhooks/github`

```bash
# Start server
uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Terminal 2: Start Redis

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
# Hoặc nếu đã có
docker start redis
```

### 4.3 Terminal 3: Start Celery Worker

```bash
cd /path/to/reviewer
uv run celery -A src.workers.celery_app worker --loglevel=info
```

---

## Bước 5: Test Indexing

### 5.1 Trigger bằng cách cài lại App

1. Vào GitHub App settings
2. Uninstall từ repo
3. Install lại vào repo

### 5.2 Xem logs

**Webhook received:**

```
[info] Installation created - triggering RAG indexing
       installation_id=12345 repos_count=1
```

**Celery worker:**

```
[info] starting_repository_index owner=your-username repo=rag-test-repo
[info] cloned_repository repo_path=/tmp/rag_index_xxx/rag-test-repo
[info] collected_files files_processed=4 files_skipped=0
[info] chunked_directory chunks_created=12
[info] completed_repository_index stats={'files_processed': 4, 'chunks_created': 12}
```

### 5.3 Verify trong Pinecone

1. Vào Pinecone dashboard
2. Chọn index `code-reviewer`
3. Xem namespace `your-username/rag-test-repo`
4. Confirm có vectors (khoảng 12 vectors)

---

## Bước 6: Test PR Review với RAG Context

### 6.1 Tạo branch mới

```bash
cd rag-test-repo
git checkout -b feature/add-percentage
```

### 6.2 Thêm function mới liên quan đến code hiện có

**Sửa file `src/order.py`:**

```python
# Thêm function mới
def calculate_percentage(items: list[Item], item_name: str) -> float:
    """Calculate percentage of total for a specific item."""
    total = calculate_total(items)  # Gọi function đã có
    item_total = sum(
        item.price * item.quantity
        for item in items
        if item.name == item_name
    )
    return (item_total / total) * 100 if total > 0 else 0
```

### 6.3 Commit và tạo PR

```bash
git add .
git commit -m "Add calculate_percentage function"
git push origin feature/add-percentage

# Tạo PR trên GitHub
```

### 6.4 Xem logs khi review

**FastAPI logs:**

```
[info] PR event received action=opened pr=1 repo=your-username/rag-test-repo
```

**Celery logs:**

```
[info] Starting review owner=your-username repo=rag-test-repo pr=1
[info] context_extractor.started pr=1 repo=your-username/rag-test-repo
[info] context_extractor.rag_enrichment_complete enriched_count=1
```

### 6.5 Kết quả mong đợi (RAG v2)

LLM sẽ nhận được context với **explicit relationships**:

```
## File: src/order.py

### Diff:
+ def calculate_percentage(items: list[Item], item_name: str) -> float:
+     total = calculate_total(items)  # Gọi function đã có
+     ...

### Related Code from Codebase:

**TEST** (tests/test_order.py): test_calculate_total
  → Test function cho calculate_total

**CALLEE** (src/order.py): calculate_total
  → Function mà calculate_percentage gọi
  def calculate_total(items: list[Item], discount: float = 0) -> float:
      ...
```

**Lưu ý RAG v2:**

- Chỉ có 3 loại relationship: `TEST`, `CALLER`, `CALLEE`
- Không có "SIMILAR" - tránh noise từ semantic similarity
- Relationships được xác định qua:
  - TEST: pattern matching (`tests/test_{name}.py`)
  - CALLER: functions có `calculate_percentage` trong `calls` metadata
  - CALLEE: functions mà `calculate_percentage` gọi (từ `calls` metadata)

---

## Bước 7: Test Incremental Update

### 7.1 Merge PR

Merge PR vào main branch.

### 7.2 Xem logs

```

[info] PR merged - triggering RAG update pr=1 repo=your-username/rag-test-repo
[info] Updated RAG index stats={'added': 0, 'modified': 1, 'removed': 0}

```

### 7.3 Verify

- Vector cho `calculate_percentage` được thêm vào Pinecone
- Vector cho `calculate_total` được update (nếu thay đổi)

---

## Troubleshooting

### RAG không hoạt động

**Check 1: Pinecone configured?**

```bash
uv run python -c "from src.rag.config import get_rag_settings; print(bool(get_rag_settings().pinecone_api_key))"
```

Expected: `True`

**Check 2: Index exists?**

```bash
uv run python -c "
from src.rag.vector_store import get_vector_store
store = get_vector_store()
print(store.describe_namespace('your-username/rag-test-repo'))
"
```

**Check 3: Webhook received?**

- Xem FastAPI logs
- Check ngrok dashboard: http://localhost:4040

### Không thấy related context

**Có thể do:**

1. File là `added` không phải `modified` → chỉ `modified` files được enrich
2. Không có functions bị thay đổi → không query RAG
3. Pinecone chưa có data → cần index trước
4. **RAG v2**: Không có test file matching pattern
5. **RAG v2**: Function không gọi hoặc được gọi bởi function khác nào

**Check RAG v2 parsing:**

```bash
uv run python -c "
from src.ast.parser import get_code_parser
parser = get_code_parser()
result = parser.parse('test.py', '''
def calculate_percentage(items, item_name):
    total = calculate_total(items)
    return total * 100
''')
print('Imports:', result.imports)
print('Calls:', result.chunks[0].calls if result.chunks else [])
"
```

Expected: `Calls: ['calculate_total']`

### Celery task failed

```bash
# Xem task error
uv run celery -A src.workers.celery_app inspect active
```

---

## Verify Checklist

- [ ] `.env` có `PINECONE_API_KEY`
- [ ] `uv sync` thành công
- [ ] Test repo đã push lên GitHub
- [ ] GitHub App đã cài vào test repo
- [ ] Ngrok đang chạy và webhook URL đã update
- [ ] FastAPI server running
- [ ] Redis running
- [ ] Celery worker running
- [ ] Logs show indexing complete
- [ ] Pinecone dashboard shows vectors
- [ ] PR review shows related context in logs
