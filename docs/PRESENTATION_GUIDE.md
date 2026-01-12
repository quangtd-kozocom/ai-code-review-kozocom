# Hướng dẫn Thuyết trình - AI Code Review với LangGraph

## Mục tiêu thuyết trình

Giúp người nghe hiểu:
1. Tại sao chọn LangGraph
2. Các điểm đột phá kỹ thuật
3. Những vấn đề đã giải quyết được

> **Lưu ý về thuật ngữ:** Trong code dùng "breaking changes" nhưng khi thuyết trình nên nói là **"thay đổi có thể gây ảnh hưởng"** hoặc **"thay đổi nguy hiểm"** - nghe nhẹ nhàng và dễ hiểu hơn.

---

## Cấu trúc thuyết trình đề xuất

### Phần 1: Vấn đề cần giải quyết (2-3 phút)

**Nên nói:**
> "Khi review PR, việc phát hiện những thay đổi có thể gây ảnh hưởng rất khó vì:
> - Một thay đổi nhỏ có thể ảnh hưởng rất nhiều file khác
> - Reviewer khó có thể nhớ hết những ai đang gọi tới function được sửa đổi
> - Review thủ công tốn thời gian và dễ bỏ sót những vấn đề như vậy"

**Ví dụ cụ thể:**
```php
// Trước: function processPayment($amount)
// Sau:   function processPayment($amount, $customerId)  // Thêm required param

// 50 files khác đang gọi processPayment($amount) → SẼ LỖI!
```

---

### Phần 2: Giải pháp - AI Reviewer am hiểu ngữ cảnh hệ thống (3-4 phút)

**Flow tổng quan:**
```
Pull Request  →  AI Reviewer  →  GitHub Comment
```

**Nên nói:**
> "Giải pháp của chúng tôi là xây dựng một AI Reviewer có khả năng hiểu ngữ cảnh toàn bộ hệ thống, không chỉ nhìn vào phần code thay đổi."

**AI Reviewer làm được gì:**
- Phân tích toàn bộ mã nguồn liên quan, không chỉ giới hạn trong phần thay đổi của PR
- Xác định các thành phần phụ thuộc và phạm vi ảnh hưởng của thay đổi
- Đánh giá mức độ rủi ro và khả năng gây lỗi tới những nơi liên quan

**Điểm khác biệt chính:**
- 🔍 **Context-aware**: Hiểu được mối quan hệ giữa các file trong codebase
- 🎯 **Impact analysis**: Tìm ra những nơi sẽ bị ảnh hưởng bởi thay đổi
- ⚠️ **Risk assessment**: Đánh giá mức độ nguy hiểm của thay đổi

---

### Phần 3: Kiến trúc Workflow với LangGraph (4-5 phút)

**Nên nói:**
> "Workflow được chia thành 3 giai đoạn chính: Preparation, Analysis và Delivery"

---

#### 🔧 Giai đoạn 1: PREPARATION

```
PR Events → Extract Diff → Clone Repo
```

**PR Events**
- Nhận webhook từ GitHub khi có PR mới (opened, synchronize)
- Trigger tự động, không cần người dùng làm gì

**Extract Diff**
- Gọi GitHub API lấy danh sách files thay đổi trong PR
- Lấy cả nội dung cũ (base) và mới (head) của từng file
- **Điểm hay**: Filter chỉ giữ code files (`.php`, `.js`, `.py`...), bỏ qua images, configs

**Clone Repo**
- Clone repo về local để search
- **Điểm hay - Tối ưu tốc độ**:
  - `--depth 1`: Chỉ clone 1 commit mới nhất
  - `--filter=blob:limit=1m`: Bỏ qua files > 1MB (images, binaries)
  - `--single-branch`: Chỉ clone branch của PR
- Kết quả: Clone nhanh, tiết kiệm dung lượng

---

#### 🧠 Giai đoạn 2: ANALYSIS (Core Logic)

```
Get Next File → Analyze File → Plan Search → Execute Search → Verify Impact → Generate Review
                                    ▲                              │
                                    └──────── Need more search ────┘
```

**Get Next File**
- Lấy file tiếp theo từ danh sách cần xử lý
- Điều phối vòng lặp: xử lý hết file này → lấy file tiếp theo
- **Điểm hay**: Xử lý file-by-file, không cần đợi hết tất cả

**Analyze File** (LLM)
- LLM đọc diff của file, phát hiện những thay đổi có thể gây ảnh hưởng
- Ví dụ: thêm required parameter, xóa function, đổi tên method
- **Điểm hay**: LLM hiểu ngữ nghĩa code, không chỉ so sánh text

**Plan Search** (LLM)
- LLM quyết định cần tìm kiếm gì để tìm những nơi gọi tới code bị thay đổi
- Output: danh sách search queries (ví dụ: `processPayment(`, `PaymentService::`)
- **Điểm hay**: LLM thông minh hơn regex cứng, biết tìm theo ngữ cảnh

**Execute Search** (Ripgrep)
- Dùng Ripgrep search trên local repo
- **Điểm hay - Tốc độ**: 
  - Tìm kiếm trong milliseconds
  - Không bị rate limit như GitHub Search API
  - Có context xung quanh mỗi kết quả

**Verify Impact** (LLM)
- LLM xem xét từng kết quả search, xác minh có thực sự bị ảnh hưởng không
- Loại bỏ false positives (comments, strings, test files...)
- **Điểm hay - Iterative Refinement**: 
  - Nếu LLM thấy cần search thêm → quay lại Plan Search
  - Giới hạn 3 lần loop để tránh infinite loop

**Generate Review** (LLM)
- Tạo review comment với format chuẩn
- Bao gồm: vấn đề gì, ảnh hưởng những file nào, recommendation

---

#### 📤 Giai đoạn 3: DELIVERY

```
Publish GitHub → (Còn file?) ──Yes──→ Get Next File
                      │
                      No (All Done)
                      ▼
              Finalize Review → Cleanup
```

**Publish GitHub**
- Post inline comment lên PR ngay lập tức
- **Điểm hay - Fast Feedback**: Developer nhận comment ngay, không cần đợi review xong toàn bộ PR
- Fallback: Nếu line không trong diff → post issue comment

**Finalize Review**
- Lưu kết quả vào Database (để tracking, analytics)
- Gửi summary qua Slack (nếu có config)

**Cleanup**
- Xóa repo đã clone khỏi temp folder
- Giải phóng disk space

---

#### Tại sao chọn LangGraph?

> "LangGraph cho phép xây dựng workflow có loop và conditional routing"

| Tính năng | Lợi ích |
|-----------|---------|
| **Loop** | Search nhiều lần nếu LLM thấy chưa đủ |
| **Conditional Routing** | Quyết định bước tiếp theo dựa trên kết quả |
| **State Management** | Theo dõi trạng thái qua nhiều bước |
| **Graceful Degradation** | Fail 1 file không ảnh hưởng file khác |

---

### Phần 4: Điểm đột phá 1 - Two-Phase Search (3-4 phút) ⭐

**ĐÂY LÀ ĐIỂM QUAN TRỌNG - NÊN NHẤN MẠNH**

**Nên nói:**
> "Chúng tôi chia việc search thành 2 phase:
> - **Phase 1 - The Brain (LLM)**: Quyết định TÌM CÁI GÌ
> - **Phase 2 - The Muscle (Ripgrep)**: Thực hiện TÌM NHƯ NÀO"

**Tại sao không dùng GitHub Search API?**
- Rate limit: 30 requests/phút
- Chậm: 200-500ms/request
- Không có context xung quanh

**Giải pháp của chúng tôi:**
- Clone repo về local (shallow clone, chỉ 1 commit)
- Dùng Ripgrep search → Tốc độ milliseconds
- Không bị rate limit

**Code minh họa (có thể show):**
```python
# LLM quyết định queries
search_plan = SearchPlan(
    queries=["processPayment(", "PaymentService::"],
    include_patterns=["*.php"],
    exclude_patterns=["*test*", "vendor/*"]
)

# Ripgrep thực thi
cmd = ["rg", "--json", "processPayment(", repo_path]
```

---

### Phần 5: Điểm đột phá 2 - Iterative Refinement (3-4 phút) ⭐

**ĐÂY LÀ ĐIỂM QUAN TRỌNG THỨ 2**

**Nên nói:**
> "Vấn đề: Những nơi gọi tới code thường bị ẩn qua Facade, Alias, hoặc Dynamic Calls.
> Giải pháp: LLM tự yêu cầu search thêm nếu thấy chưa đủ."

**Diagram:**
```
Search Code → Analyze Result → Cần search thêm? 
     ↑              │                │
     │              │           Yes  │  No
     │              │                │
     └──────────────┘                ▼
                              Generate Review
```

**Ví dụ thực tế:**
```
Lần 1: Search "processPayment(" → Tìm được 10 files
Lần 2: LLM thấy có PaymentFacade → Search "PaymentFacade::" → Thêm 5 files
Lần 3: Đủ confident → Dừng
```

**An toàn:**
- Giới hạn MAX_SEARCH_ITERATIONS = 3
- Tránh infinite loop

---

### Phần 6: Tối ưu hiệu năng (2-3 phút)

**Nên nói:**
> "Workflow được thiết kế để nhanh và không block"

**4 điểm chính:**

1. **File-by-File Processing**
   - Xử lý từng file, post comment ngay
   - Developer nhận feedback sớm

2. **Fast Feedback Loop**
   - Không cần đợi review xong toàn bộ PR

3. **Shallow Clone & Blob Filter**
   - `--depth 1`: Chỉ clone 1 commit
   - `--filter=blob:limit=1m`: Bỏ qua file lớn (images, binaries)

4. **Graceful Degradation**
   - Nếu LLM fail ở 1 file → Các file khác vẫn được review

---

### Phần 7: Kết quả đạt được (2 phút)

**Nên nói:**
> "Hệ thống đã giải quyết được:"

| Vấn đề | Giải pháp |
|--------|-----------|
| Không biết ai đang gọi function | LLM + Ripgrep tìm tất cả callers |
| Review chậm | File-by-file + Immediate publishing |
| Bỏ sót thay đổi nguy hiểm | Iterative search đến khi đủ confident |
| Rate limit GitHub API | Local search với Ripgrep |
| Khó maintain workflow phức tạp | LangGraph declarative graph |

---

## Những phần NÊN BỎ QUA (không cần đi sâu)

1. **Chi tiết implementation của từng node** - Chỉ cần nói concept
2. **Prompts chi tiết** - Chỉ mention là dùng structured output
3. **Database schema** - Không liên quan đến LangGraph
4. **Slack/GitHub integration** - Đây là phần publish, không phải core
5. **Multi-language support** - Nice to have, không phải điểm chính

---

## Tips thuyết trình

### Nên làm:
- ✅ Show diagram workflow
- ✅ Dùng ví dụ cụ thể (processPayment)
- ✅ So sánh trước/sau
- ✅ Demo nếu có thể

### Không nên:
- ❌ Đọc code chi tiết
- ❌ Giải thích từng dòng prompt
- ❌ Nói về infrastructure (Redis, Celery)

---

## Câu hỏi có thể được hỏi

**Q: Tại sao không dùng RAG/Vector search?**
> A: Ripgrep cho exact match nhanh hơn và chính xác hơn cho use case tìm function calls. RAG phù hợp hơn cho semantic search.

**Q: LLM có thể sai không?**
> A: Có, nhưng chúng tôi dùng structured output (Pydantic) để validate, và có fallback khi LLM fail.

**Q: Tốn bao nhiêu token?**
> A: Tùy PR size, trung bình 2000-5000 tokens/file. Dùng GPT-4o-mini để tiết kiệm.

**Q: Sao không dùng AST parsing thay vì Ripgrep?**
> A: AST chính xác hơn nhưng phức tạp và chậm hơn. Ripgrep + LLM verification đủ tốt cho use case này.

---

## Thời lượng đề xuất

| Phần | Thời gian |
|------|-----------|
| Vấn đề cần giải quyết | 2-3 phút |
| Giải pháp - AI Reviewer | 3-4 phút |
| Kiến trúc Workflow + LangGraph | 4-5 phút |
| Two-Phase Search ⭐ | 3-4 phút |
| Iterative Refinement ⭐ | 3-4 phút |
| Tối ưu hiệu năng | 2-3 phút |
| Kết quả | 2 phút |
| Q&A | 5 phút |
| **Tổng** | **~25-30 phút** |

---

## Key Takeaways (Kết luận)

Khi kết thúc, nhấn mạnh 3 điểm:

1. **LangGraph** cho phép xây dựng workflow phức tạp với loop và conditional routing
2. **Two-Phase Search** (LLM + Ripgrep) giải quyết vấn đề rate limit và tốc độ
3. **Iterative Refinement** đảm bảo không bỏ sót những nơi gọi tới code bị thay đổi

> "Kết hợp sức mạnh của LLM (reasoning) với công cụ truyền thống (Ripgrep) để tạo ra hệ thống review code thông minh và nhanh."
