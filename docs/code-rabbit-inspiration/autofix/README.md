# 🐰 CodeRabbit Inspiration - Auto-Fix

Tài liệu hướng dẫn implement tính năng Auto-Fix theo phong cách CodeRabbit cho dự án AI Code Reviewer.

## 📂 Nội Dung

| File                                     | Mô Tả                                           |
| ---------------------------------------- | ----------------------------------------------- |
| [ARCHITECTURE.md](./ARCHITECTURE.md)     | Kiến trúc tổng quan và so sánh với MVP hiện tại |
| [IMPLEMENTATION.md](./IMPLEMENTATION.md) | Hướng dẫn implement chi tiết từng bước          |
| [COMMANDS.md](./COMMANDS.md)             | Danh sách commands hỗ trợ                       |

## 🎯 Tóm Tắt

CodeRabbit **tách riêng** 2 luồng:

1. **Auto Review** - Passive, chỉ comment về issues
2. **Finishing Touches** - On-demand, generate code khi user yêu cầu

Chúng ta sẽ áp dụng pattern này vào dự án.
