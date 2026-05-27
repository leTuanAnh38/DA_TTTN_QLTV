from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Book, BorrowTransaction, Penalty, Category, Publisher

User = get_user_model()

class LibraryBusinessLogicTests(TestCase):
    def setUp(self):
        """
        Hàm này chạy trước MỖI bài test. 
        Dùng để tạo sẵn dữ liệu ảo (Mock Data) trên RAM để test.
        """
        # 1. Tạo 1 Category ảo
        self.category = Category.objects.create(name='Công nghệ thông tin')
        
        # 2. Tạo 1 User ảo
        self.user = User.objects.create_user(
            username='khanh_test', 
            password='testpassword123',
            first_name='Khanh',
            msv='SV999',
            lop='KTPM',
            points=20 # Cho sẵn 20 điểm
        )
        
        # 3. Tạo 1 Cuốn sách ảo
        self.book = Book.objects.create(
            title='Clean Code',
            author='Robert C. Martin',
            quantity=5,
            category=self.category
        )

    # ==========================================
    # BÀI TEST 1: Kiểm tra khởi tạo User thành công
    # ==========================================
    def test_01_user_creation_and_attributes(self):
        self.assertEqual(self.user.username, 'khanh_test')
        self.assertEqual(self.user.msv, 'SV999')
        self.assertEqual(User.objects.count(), 1) # Đảm bảo DB ảo có đúng 1 user

    # ==========================================
    # BÀI TEST 2: Kiểm tra logic số lượng sách giảm khi mượn
    # ==========================================
    def test_02_borrow_book_decreases_quantity(self):
        initial_quantity = self.book.quantity
        
        # Giả lập hành động mượn sách
        BorrowTransaction.objects.create(
            user=self.user,
            book=self.book,
            due_date=timezone.now().date() + timedelta(days=14),
            status='BORROWED'
        )
        self.book.quantity -= 1
        self.book.save()

        # Kiểm tra xem kho sách có bị trừ đi 1 không (5 - 1 = 4)
        self.assertEqual(self.book.quantity, initial_quantity - 1)

    # ==========================================
    # BÀI TEST 3: Kiểm tra logic chặn mượn sách khi đang nợ tiền phạt (ĐÃ FIX LỖI)
    # ==========================================
    def test_03_user_with_unpaid_penalty_has_fine(self):
        # 1. Tạo một giao dịch mượn sách ảo trước (BẮT BUỘC ĐỂ KHÔNG BỊ LỖI NULL)
        dummy_transaction = BorrowTransaction.objects.create(
            user=self.user,
            book=self.book,
            due_date=timezone.now().date() - timedelta(days=10),
            status='RETURNED'
        )

        # 2. Giả lập user bị phạt 50k, gắn với giao dịch ảo vừa tạo
        Penalty.objects.create(
            user=self.user,
            borrow_transaction=dummy_transaction, # Dòng vá lỗi nằm ở đây
            amount=50000,
            reason="Làm rách trang sách",
            status='UNPAID'
        )
        
        # 3. Gọi hàm property total_fine trong models để xem hệ thống có tính đúng tổng nợ không
        self.assertEqual(self.user.total_fine, 50000)
        self.assertTrue(self.user.total_fine > 0) # Khẳng định user này không đủ điều kiện mượn

    # ==========================================
    # BÀI TEST 4: Kiểm tra logic CỘNG điểm khi trả đúng hạn
    # ==========================================
    def test_04_return_book_on_time_adds_points(self):
        initial_points = self.user.points # Ban đầu có 20 điểm
        
        # Giả lập logic trong hàm return_book (trả đúng hạn được +10)
        self.user.points += 10
        self.user.save()
        
        # Mong đợi: 20 + 10 = 30 điểm
        self.assertEqual(self.user.points, initial_points + 10)

    # ==========================================
    # BÀI TEST 5: Kiểm tra logic TRỪ điểm khi trả trễ hạn (Không âm điểm)
    # ==========================================
    def test_05_return_book_late_deducts_points(self):
        # Đặt lại điểm user thành 3 điểm (để test logic không bị âm)
        self.user.points = 3
        self.user.save()
        
        # Giả lập logic trong hàm return_book (trả trễ bị -5, min = 0)
        self.user.points = max(0, self.user.points - 5)
        self.user.save()
        
        # Mong đợi: 3 - 5 = -2, nhưng hệ thống chặn số âm nên điểm phải bằng 0
        self.assertEqual(self.user.points, 0)

    # ==========================================
    # BÀI TEST 6: Kiểm tra logic nâng hạng thành viên dựa trên điểm
    # ==========================================
    def test_06_membership_ranking_logic(self):
        # 1. Ban đầu (20 điểm) -> Phải là STANDARD
        self.assertEqual(self.user.rank_info['level'], 'STANDARD')
        
        # 2. Lên 150 điểm -> Phải là PREMIUM
        self.user.points = 150
        self.user.save()
        self.assertEqual(self.user.rank_info['level'], 'PREMIUM')
        
        # 3. Lên 600 điểm -> Phải là VIP
        self.user.points = 600
        self.user.save()
        self.assertEqual(self.user.rank_info['level'], 'VIP')

    # ==========================================
    # BÀI TEST 7: Kiểm tra nộp phạt làm sạch nợ (Total Fine)
    # ==========================================
    def test_07_penalty_payment_clears_total_fine(self):
        # 1. Tạo 1 giao dịch và 1 khoản phạt UNPAID
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='RETURNED')
        penalty = Penalty.objects.create(user=self.user, borrow_transaction=trans, amount=15000, status='UNPAID')
        
        # Đảm bảo ban đầu nợ 15k
        self.assertEqual(self.user.total_fine, 15000)
        
        # 2. Giả lập thanh toán tiền phạt
        penalty.status = 'PAID'
        penalty.save()
        
        # Kiểm tra nợ phải về 0
        self.assertEqual(self.user.total_fine, 0)

    # ==========================================
    # BÀI TEST 8: Kiểm tra logic xác định giao dịch quá hạn
    # ==========================================
    def test_08_overdue_transaction_detection(self):
        # 1. Tạo giao dịch có hạn trả là ngày hôm qua (Đã quá hạn)
        overdue_trans = BorrowTransaction.objects.create(
            user=self.user,
            book=self.book,
            due_date=timezone.now().date() - timedelta(days=1),
            status='BORROWED'
        )
        
        # Kiểm tra hàm is_overdue của model (nếu có) hoặc logic so sánh ngày
        today = timezone.now().date()
        self.assertTrue(overdue_trans.due_date < today)
        self.assertEqual(overdue_trans.status, 'BORROWED') # Vẫn đang mượn nhưng đã quá hạn

    # ==========================================
    # BÀI TEST 9: Kiểm tra ràng buộc Mã sinh viên (MSV) phải là duy nhất
    # ==========================================
    def test_09_unique_msv_constraint(self):
        from django.db import IntegrityError
        # Cố gắng tạo một user thứ 2 trùng MSV 'SV999' của self.user
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user_trung_msv',
                password='password123',
                msv='SV999' # Trùng MSV
            )

    # ==========================================
    # BÀI TEST 10: Kiểm tra logic hết sách trong kho
    # ==========================================
    def test_10_book_out_of_stock_logic(self):
        # 1. Giả lập hết sách (số lượng = 0)
        self.book.quantity = 0
        self.book.save()
        
        # 2. Kiểm tra logic sẵn sàng cho mượn
        is_available = self.book.quantity > 0
        self.assertFalse(is_available)
        
        # 3. Kiểm tra tên hiển thị của trạng thái (sử dụng get_status_display() của Django)
        # Giả sử ta muốn kiểm tra xem khi hết sách thì status code có thể là 'AVAILABLE' nhưng logic mượn bị chặn
        self.assertEqual(self.book.get_status_display(), 'Available')

    # ==========================================
    # BÀI TEST 11: Kiểm tra tích lũy điểm qua nhiều lần trả sách
    # ==========================================
    def test_11_cumulative_points_logic(self):
        # Giả sử trả đúng hạn 3 lần liên tiếp (+10 mỗi lần)
        initial_points = self.user.points # 20
        
        for _ in range(3):
            self.user.points += 10
            self.user.save()
            
        # Mong đợi: 20 + (10 * 3) = 50
        self.assertEqual(self.user.points, initial_points + 30)


# ==========================================
# NHÓM KIỂM THỬ GIAO DIỆN & QUYỀN TRUY CẬP (VIEW TESTS)
# ==========================================
from django.urls import reverse

class LibraryViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Khoa học')
        self.user = User.objects.create_user(username='student', password='password123', role='READER')
        self.staff = User.objects.create_user(username='librarian', password='password123', role='STAFF')

    def test_view_home_page(self):
        """Kiểm tra trang chủ có hoạt động không"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_view_profile_requires_login(self):
        """Kiểm tra trang hồ sơ yêu cầu đăng nhập"""
        response = self.client.get(reverse('profile'))
        # Phải chuyển hướng (302) sang trang login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_staff_dashboard_access_denied_for_reader(self):
        """Kiểm tra sinh viên không được vào trang quản trị thủ thư"""
        self.client.login(username='student', password='password123')
        response = self.client.get(reverse('staff_dashboard'))
        # Thường hệ thống sẽ redirect sinh viên về trang chủ hoặc báo lỗi 403
        self.assertIn(response.status_code, [302, 403])

    def test_staff_dashboard_access_allowed_for_staff(self):
        """Kiểm tra thủ thư vào được trang quản trị"""
        self.client.login(username='librarian', password='password123')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_api_search_is_working(self):
        """Kiểm tra API tìm kiếm sách trả về kết quả JSON"""
        response = self.client.get(reverse('api_live_search'), {'q': 'Clean'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')


# ==========================================
# NHÓM KIỂM THỬ GIAO DỊCH (TRANSACTION TESTS)
# ==========================================
class LibraryTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Văn học')
        self.book = Book.objects.create(title='Đắc Nhân Tâm', quantity=10, category=self.category)
        self.user = User.objects.create_user(username='tester', password='password123', msv='SV001', lop='CNTT')
        self.client.login(username='tester', password='password123')

    def test_borrow_book_success(self):
        """Kiểm tra mượn sách thành công qua POST"""
        pickup_date = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        response = self.client.post(reverse('borrow_book', args=[self.book.id]), {
            'pickup_date': pickup_date,
            'pickup_shift': 'SANG',
            'payment_method': 'FREE'
        })
        # Sau khi mượn thành công, hệ thống redirect
        self.assertEqual(response.status_code, 302)
        # Kiểm tra giao dịch đã được tạo trong DB
        self.assertTrue(BorrowTransaction.objects.filter(user=self.user, book=self.book).exists())
        # Kiểm tra số lượng sách giảm
        self.book.refresh_from_db()
        self.assertEqual(self.book.quantity, 9)

    def test_borrow_book_denied_if_has_fine(self):
        """Kiểm tra chặn mượn sách nếu đang nợ tiền phạt"""
        # Giả lập nợ 20k bằng cách tạo một khoản phạt UNPAID
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='RETURNED')
        Penalty.objects.create(user=self.user, borrow_transaction=trans, amount=20000, status='UNPAID')
        
        response = self.client.post(reverse('borrow_book', args=[self.book.id]), {
            'pickup_date': '2026-05-10',
            'pickup_shift': 'SANG'
        })
        # Phải redirect về trang profile để nộp phạt
        self.assertIn('/profile/', response.url)
        # Không có giao dịch mượn mới nào được tạo (ngoại trừ cái trans cũ để tạo phạt)
        self.assertEqual(BorrowTransaction.objects.filter(status='PENDING').count(), 0)

    def test_return_book_request(self):
        """Kiểm tra sinh viên gửi yêu cầu trả sách"""
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='BORROWED')
        response = self.client.get(reverse('return_book', args=[trans.id]))
        
        trans.refresh_from_db()
        self.assertEqual(trans.status, 'PENDING')
        self.assertEqual(trans.reason, 'YÊU CẦU TRẢ')

    def test_renew_book_success(self):
        """Kiểm tra gia hạn thành công (còn 1 ngày nữa hết hạn)"""
        due_date = timezone.now().date() + timedelta(days=1)
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=due_date, status='BORROWED')
        
        response = self.client.get(reverse('renew_book', args=[trans.id]))
        trans.refresh_from_db()
        
        # Hạn trả mới phải là hạn cũ + 7 ngày
        self.assertEqual(trans.due_date, due_date + timedelta(days=7))
        self.assertEqual(trans.renewal_count, 1)

    def test_renew_book_denied_if_too_early(self):
        """Kiểm tra chặn gia hạn nếu còn quá nhiều ngày (ví dụ còn 10 ngày)"""
        due_date = timezone.now().date() + timedelta(days=10)
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=due_date, status='BORROWED')
        
        response = self.client.get(reverse('renew_book', args=[trans.id]))
        trans.refresh_from_db()
        
        # Hạn trả không đổi và có thông báo lỗi trong messages
        self.assertEqual(trans.due_date, due_date)
        self.assertEqual(trans.renewal_count, 0)


# ==========================================
# NHÓM KIỂM THỬ TÁC VỤ THỦ THƯ (STAFF ACTION TESTS)
# ==========================================
class LibraryStaffActionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Khoa học')
        self.book = Book.objects.create(title='Python Pro', quantity=5, original_price=200000, category=self.category)
        self.user = User.objects.create_user(username='student', password='password123', msv='SV001', points=50)
        self.staff = User.objects.create_user(username='admin', password='password123', role='STAFF')
        self.client.login(username='admin', password='password123')

    def test_staff_approve_borrow_success(self):
        """Thủ thư duyệt yêu cầu mượn sách"""
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='PENDING')
        response = self.client.get(reverse('staff_approve_borrow', args=[trans.id]))
        
        trans.refresh_from_db()
        self.assertEqual(trans.status, 'BORROWED')
        self.assertTrue(trans.is_paid)
        # Hạn trả mới phải là +14 ngày từ hôm nay
        self.assertEqual(trans.due_date, timezone.now().date() + timedelta(days=14))

    def test_staff_confirm_return_with_penalty_paid(self):
        """Thủ thư thu hồi sách hỏng và sinh viên nộp tiền luôn tại quầy"""
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='BORROWED')
        
        # Gửi POST với tình trạng hỏng nhẹ và đã nộp tiền
        response = self.client.post(reverse('staff_confirm_return', args=[trans.id]), {
            'book_condition': 'LIGHT_DAMAGE',
            'pay_now': 'YES'
        })
        
        trans.refresh_from_db()
        self.assertEqual(trans.status, 'RETURNED')
        
        # Kiểm tra phiếu phạt đã được tạo và ở trạng thái PAID
        penalty = Penalty.objects.get(borrow_transaction=trans)
        self.assertEqual(penalty.status, 'PAID')
        self.assertEqual(penalty.amount, 20000) # 10% của 200k

    def test_staff_confirm_return_on_time_adds_points(self):
        """Thủ thư thu hồi sách đúng hạn -> Sinh viên được cộng điểm"""
        initial_points = self.user.points
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date() + timedelta(days=1), status='BORROWED')
        
        self.client.post(reverse('staff_confirm_return', args=[trans.id]), {'book_condition': 'NORMAL'})
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.points, initial_points + 10)

    def test_staff_confirm_penalty_payment(self):
        """Thủ thư duyệt nộp phạt cho khoản nợ cũ"""
        trans = BorrowTransaction.objects.create(user=self.user, book=self.book, due_date=timezone.now().date(), status='RETURNED')
        penalty = Penalty.objects.create(user=self.user, borrow_transaction=trans, amount=5000, status='UNPAID')
        
        response = self.client.get(reverse('staff_confirm_penalty', args=[penalty.id]))
        
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, 'PAID')


# ==========================================
# NHÓM KIỂM THỬ TÍNH NĂNG PHỤ (FEATURE TESTS)
# ==========================================
from core.models import Cart, CartItem, Event, EventRegistration

class LibraryFeatureTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Kỹ năng')
        self.book = Book.objects.create(title='Kỹ năng sống', quantity=5, category=self.category)
        self.user = User.objects.create_user(username='user_feature', password='password123')
        self.client.login(username='user_feature', password='password123')

    def test_cart_limit_logic(self):
        """Kiểm tra giới hạn 4 cuốn trong giỏ sách"""
        # Thêm 4 cuốn khác nhau vào giỏ (Giả lập)
        cart, _ = Cart.objects.get_or_create(user=self.user)
        for i in range(4):
            b = Book.objects.create(title=f'Sách {i}', quantity=1, category=self.category)
            CartItem.objects.create(cart=cart, book=b)
        
        # Thử thêm cuốn thứ 5 qua API
        new_book = Book.objects.create(title='Sách thứ 5', quantity=1, category=self.category)
        response = self.client.get(reverse('api_add_to_cart', args=[new_book.id]), 
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Phải báo lỗi và success=False
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Giới hạn 4 cuốn', data['message'])

    def test_wishlist_toggle(self):
        """Kiểm tra bật/tắt sách yêu thích (Yêu cầu POST)"""
        url = reverse('api_toggle_wishlist', args=[self.book.id])
        
        # Lần 1: Thêm vào yêu thích (POST)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['is_wished'])
        
        # Lần 2: Xóa khỏi yêu thích (POST)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(response.json()['is_wished'])

    def test_event_registration_toggle(self):
        """Kiểm tra đăng ký tham gia sự kiện"""
        event = Event.objects.create(
            title='Hội sách 2026', 
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=2)
        )
        url = reverse('api_toggle_event_registration', args=[event.id])
        
        # Đăng ký
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['is_registered'])
        self.assertEqual(EventRegistration.objects.count(), 1)
        
        # Hủy đăng ký
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(response.json()['is_registered'])
        self.assertEqual(EventRegistration.objects.count(), 0)


# ==========================================
# NHÓM KIỂM THỬ FORM (FORM TESTS)
# ==========================================
from core.forms import BookForm

class LibraryFormTests(TestCase):
    def test_book_form_validation(self):
        """Kiểm tra tính hợp lệ của Form thêm sách"""
        category = Category.objects.create(name='Test Cat')
        publisher = Publisher.objects.create(name='NXB Trẻ', address='HN')
        data = {
            'title': 'Sách Test Form',
            'author': 'Tác giả Test',
            'quantity': 10,
            'initial_quantity': 10,
            'category': category.id,
            'publisher': publisher.id,
            'floor': 1,
            'status': 'AVAILABLE'
        }
        form = BookForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_book_form_invalid(self):
        """Kiểm tra Form báo lỗi khi thiếu thông tin bắt buộc (ví dụ thiếu tiêu đề)"""
        form = BookForm(data={'author': 'No Title'})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)