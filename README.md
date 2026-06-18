# 📚 Alovu - Hệ Thống website Quản Lý Thư Viện 
Lớp 22CT2
Thành Viên:
          Lê Tuấn Anh
          Nguyễn Chí Trung

Alovu là một hệ thống quản lý thư viện hiện đại được xây dựng bằng **Django Framework**. Dự án cung cấp giải pháp toàn diện để số hóa quy trình mượn/trả sách, quản lý kho tài liệu, thu phí phạt và tự động hóa các tác vụ quản trị cho thủ thư.

## ✨ Tính Năng Nổi Bật

### 🎓 Dành cho Người dùng (Sinh viên/Độc giả)
* **Khám phá tài liệu:** Tìm kiếm sách theo từ khóa, danh mục, sách mới, sách thịnh hành và sách có phí (Premium).
* **Giỏ đăng ký mượn (Database-driven):** Thêm nhiều sách vào giỏ, chọn ngày giờ đến lấy (Ca Sáng/Chiều) và phương thức thanh toán. Giỏ hàng được lưu trữ vĩnh viễn trên database.
* **Gia hạn trực tuyến:** Tự động gia hạn sách (tối đa 2 lần) với điều kiện kiểm tra chặt chẽ.
* **Hồ sơ cá nhân:** Quản lý thông tin, theo dõi lịch sử mượn/trả, sách yêu thích (Wishlist) và điểm thưởng.
* **Thanh toán & Nợ phạt:** Tích hợp thanh toán phí phạt (hư hỏng, mất sách, trễ hạn) qua quét mã QR hoặc tiền mặt.
* **Hộp thư thông báo (Real-time tracking):** Nhận cảnh báo sắp đến hạn, thông báo trễ hạn, và xác nhận giao dịch.
* **Đánh giá & Nhận xét:** Để lại review sao và bình luận cho các cuốn sách đã mượn.
* **Sự kiện:** Theo dõi và đăng ký tham gia các sự kiện do thư viện tổ chức.

### 🛡️ Dành cho Quản trị viên (Thủ thư/Admin)
* **Bảng điều khiển (Dashboard):** Thống kê tổng quan sách trong kho, đơn chờ duyệt, đơn đang mượn và đơn quá hạn.
* **Quản lý Mượn/Trả:** Duyệt đơn online, xác nhận thu hồi sách, đánh giá tình trạng vật lý của sách lúc nhận (Bình thường/Hư hỏng/Mất) để tự động tính phí phạt.
* **Quản lý Kho sách & Danh mục:** Thêm, sửa, xóa tài liệu, tác giả, nhà xuất bản.
* **Quản lý Độc giả:** Theo dõi hồ sơ mượn sách, điểm uy tín và tổng nợ của từng cá nhân.
* **Hệ thống tự động hóa (APScheduler):** Tự động chạy ngầm để quét sách quá hạn và tự động hủy các đơn hẹn mượn nhưng sinh viên không đến lấy (quá 12h trưa ca Sáng hoặc 18h tối ca Chiều).

## 🛠️ Công Nghệ Sử Dụng
* **Back-end:** Python, Django Framework.
* **Cơ sở dữ liệu:** MySQL.
* **Front-end:** HTML5, CSS3, Bootstrap 5, JavaScript, FontAwesome.
* **Tác vụ nền (Background Jobs):** APScheduler (Tự động hóa hủy đơn và thông báo).

## 🚀 Hướng Dẫn Cài Đặt (Local Development)

Làm theo các bước sau để chạy dự án trên máy cá nhân của bạn:

**Bước 1: Clone kho lưu trữ về máy**
```bash
git clone [https://github.com//leTuanAnh38/library-management-system.git](https://github.com//leTuanAnh38/library-management-system.git)
cd library-management-system
```

**Bước 2: Tạo môi trường ảo (Virtual Environment) và kích hoạt**
```bash
python -m venv venv
# Dành cho Windows:
venv\Scripts\activate
# Dành cho macOS/Linux:
source venv/bin/activate
```

**Bước 3: Cài đặt các thư viện cần thiết**
```bash
pip install -r requirements.txt
```

**Bước 4: Cập nhật cơ sở dữ liệu (Migrations)**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Bước 5: Tạo tài khoản Admin**
```bash
python manage.py createsuperuser
```

**Bước 6: Khởi chạy máy chủ**
```bash
python manage.py runserver
```
Sau khi chạy lệnh trên, truy cập `http://127.0.0.1:8000/` để xem trang web và `http://127.0.0.1:8000/admin/` để vào hệ thống quản trị.

---
*Dự án được phát triển nhằm mục đích phục vụ đồ án môn học và tối ưu hóa trải nghiệm mượn trả tài liệu tại thư viện.*
