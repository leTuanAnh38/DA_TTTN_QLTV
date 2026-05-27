from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.urls import reverse
from django.db.models import Sum

# Lớp cơ sở để tái sử dụng created_at và updated_at cho tất cả các bảng
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# 1. Bảng USERS
class User(AbstractUser, TimeStampedModel):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('STAFF', 'Staff'),
        ('READER', 'Reader'),
    )
    MEMBERSHIP_CHOICES = (
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('VIP', 'VIP'),
    )
    
    dob = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='READER')
    membership_level = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='STANDARD')
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', null=True, blank=True)
    msv = models.CharField(max_length=20, unique=True, verbose_name="Mã sinh viên", null=True, blank=True)
    lop = models.CharField(max_length=50, verbose_name="Lớp", null=True, blank=True)
    dia_chi = models.TextField(verbose_name="Địa chỉ", null=True, blank=True)
    points = models.IntegerField(default=0, verbose_name="Điểm tích lũy")

    @property
    def rank_info(self):
        """Xác định hạng và quyền lợi dựa trên số điểm tích lũy"""
        if self.points >= 500:
            return {'level': 'VIP', 'max_books': 6, 'color': 'text-danger', 'next': None}
        elif self.points >= 100:
            return {'level': 'PREMIUM', 'max_books': 5, 'color': 'text-primary', 'next': 500}
        else:
            return {'level': 'STANDARD', 'max_books': 4, 'color': 'text-success', 'next': 100}

    @property
    def avatar_url(self):
        """Trả về URL ảnh nếu có, nếu không trả về ảnh mặc định"""
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        # Đường dẫn ảnh mặc định trong thư mục static của Khanh
        from django.templatetags.static import static
        return static('img/avatar.png')
    @property
    def total_fine(self):
        # Tính tổng tiền từ bảng Penalty của những khoản chưa thanh toán (giả sử status là 'UNPAID')
        from .models import Penalty # Tránh import vòng quanh
        total = Penalty.objects.filter(user=self, status='UNPAID').aggregate(Sum('amount'))['amount__sum']
        return total if total else 0

    class Meta:
        verbose_name = 'Người dùng'
        verbose_name_plural = 'Danh sách Người dùng'

    def __str__(self):
        return self.username

# 2. Bảng CATEGORIES
class Category(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(null=True, blank=True)
    class Meta:
        verbose_name = 'Danh mục sách'
        verbose_name_plural = 'Các Danh mục sách'

    def __str__(self):
        return self.name

# 3. Bảng PUBLISHERS
class Publisher(TimeStampedModel):
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Nhà xuất bản'
        verbose_name_plural = 'Các Nhà xuất bản'

    def __str__(self):
        return self.name

# 4. Bảng BOOKS
class Book(TimeStampedModel):
    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
        ('LOST', 'Lost'),
    )

    title = models.CharField(max_length=255)
    location = models.CharField(max_length=100, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='books')
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, related_name='books')
    cover_image = models.CharField(max_length=255, null=True, blank=True)
    cover_file = models.ImageField(upload_to='books/covers/', blank=True, null=True)
    author = models.CharField(max_length=150, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Giá thuê sách (nếu có)")
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Giá gốc của sách")
    initial_quantity = models.IntegerField(default=0)
    quantity = models.IntegerField(default=0)
    published_year = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    floor = models.IntegerField(default=1, verbose_name="Tầng")
    shelf = models.CharField(max_length=50, blank=True, verbose_name="Kệ sách")
    area = models.CharField(max_length=100, blank=True, verbose_name="Khu vực/Phòng")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    class Meta:
        verbose_name = 'Cuốn sách'
        verbose_name_plural = 'Kho Sách'

    def __str__(self):
        return self.title
    @property
    def get_cover(self):
        """Hàm này sẽ tự động kiểm tra: Nếu có file upload thì lấy url của file, nếu không có thì lấy link mạng"""
        if self.cover_file:
            return self.cover_file.url
        if self.cover_image:
            return self.cover_image
        return "https://placehold.co/150x220?text=Chua+Co+Anh" # Ảnh mặc định nếu sách không có ảnh

# 5. Bảng BOOK_IMAGES
class BookImage(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='images')
    image_url = models.CharField(max_length=255)

# 6. Bảng BORROW_TRANSACTIONS
class BorrowTransaction(TimeStampedModel):
    STATUS_CHOICES = (
        ('BORROWED', 'Đang mượn'),
        ('PENDING', 'Chờ xác nhận'), # Dùng cho cả: Chờ duyệt TRẢ sách và Chờ duyệt MƯỢN
        ('RETURNED', 'Đã trả'),
        ('OVERDUE', 'Quá hạn'),
        ('CANCELLED', 'Đã hủy hẹn'), # ---> [MỚI THÊM] Trạng thái khi hệ thống tự động hủy
    )

    # ==========================================
    # [MỚI THÊM] Các lựa chọn ca lấy sách
    # ==========================================
    SHIFT_CHOICES = (
        ('SANG', 'Buổi Sáng (07:30 - 11:30)'),
        ('CHIEU', 'Buổi Chiều (13:00 - 17:00)'),
    )

    # ==========================================
    # Các lựa chọn phương thức thanh toán
    # ==========================================
    PAYMENT_CHOICES = (
        ('FREE', 'Miễn phí'),
        ('CASH', 'Thanh toán tại quầy'),
        ('BANK', 'Chuyển khoản ngân hàng'),
    )

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrow_records')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_records')
    
    borrow_date = models.DateField(auto_now_add=True, verbose_name="Ngày mượn")
    due_date = models.DateField(null=True, blank=True, verbose_name="Hạn trả")
    return_date = models.DateField(null=True, blank=True, verbose_name="Ngày trả thực tế")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BORROWED')
    reason = models.CharField(max_length=255, null=True, blank=True)
    # ==========================================
    # [MỚI THÊM] Trường lưu thông tin hẹn lấy sách
    # ==========================================
    pickup_date = models.DateField(null=True, blank=True, verbose_name="Ngày hẹn lấy")
    pickup_shift = models.CharField(max_length=10, choices=SHIFT_CHOICES, null=True, blank=True, verbose_name="Ca hẹn lấy")
    # ==========================================
    # Trường lưu thông tin thanh toán
    # ==========================================
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='FREE', verbose_name="Phương thức thanh toán")
    is_paid = models.BooleanField(default=False, verbose_name="Trạng thái thanh toán")
    renewal_count = models.IntegerField(default=0, verbose_name="Số lần gia hạn")

    @property
    def is_late(self):
        """Kiểm tra xem giao dịch này có bị trả trễ không"""
        if self.return_date and self.due_date:
            return self.return_date > self.due_date
        elif not self.return_date and self.due_date:
            return timezone.now().date() > self.due_date
        return False

    @property
    def penalty_amount(self):
        """Lấy số tiền phạt của giao dịch này (nếu có)"""
        try:
            penalty = self.penalty_set.first() 
            return penalty.amount if penalty else 0
        except AttributeError:
            penalty = self.penalties.first()
            return penalty.amount if penalty else 0

    def __str__(self):
        return f"{self.user.username} mượn '{self.book.title}'"

    class Meta:
        verbose_name = 'Giao dịch mượn'
        verbose_name_plural = 'Quản lý Mượn/Trả'
        
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Giỏ sách của {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'book') # Không cho phép thêm 1 cuốn sách 2 lần vào giỏ

class Penalty(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='penalties')
    borrow_transaction = models.ForeignKey(BorrowTransaction, on_delete=models.CASCADE, related_name='penalties')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    due_date = models.DateField(null=True, blank=True)
    PAYMENT_METHODS = (
        ('COUNTER', 'Tại quầy'),
        ('TRANSFER', 'Chuyển khoản'),
    )
    # ... các trường cũ (user, amount, reason...) ...
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    # --- THÊM PHẦN NÀY VÀO ---
    STATUS_CHOICES = [
        ('UNPAID', 'Chưa thanh toán'),
        ('PAID', 'Đã thanh toán'),
    ]
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='UNPAID',
        verbose_name="Trạng thái"
    )
    # ------------------------

    class Meta:
        verbose_name = 'Phiếu phạt'
        verbose_name_plural = 'Danh sách Xử phạt'

# 8. Bảng REVIEWS
class Review(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.SmallIntegerField() 
    comment = models.TextField(null=True, blank=True)
    class Meta:
        verbose_name = 'Đánh giá'
        verbose_name_plural = 'Danh sách Đánh giá'

# 9. Bảng WISHLISTS
class Wishlist(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='wishlisted_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    class Meta:
        verbose_name = 'Yêu thích'
        verbose_name_plural = 'Danh sách Yêu thích'

# 10. Bảng RECOMMENDATIONS
class Recommendation(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='recommendations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommended_to')
    score = models.FloatField()
    class Meta:
        verbose_name = 'Đề xuất sách'
        verbose_name_plural = 'Danh sách Đề xuất'

# 11. Bảng MEMBERSHIPS
class Membership(TimeStampedModel):
    LEVEL_CHOICES = (
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('VIP', 'VIP'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='STANDARD')
    points = models.IntegerField(default=0)
    class Meta:
        verbose_name = 'Hạng thành viên'
        verbose_name_plural = 'Quản lý Hạng thành viên'

# 12. Bảng NOTIFICATIONS
class Notification(TimeStampedModel):
    TYPE_CHOICES = (
        ('REMINDER', 'Reminder'),
        ('WARNING', 'Warning'),
        ('SYSTEM', 'System'),
    )
    STATUS_CHOICES = (
        ('UNREAD', 'Unread'),
        ('READ', 'Read'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SYSTEM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNREAD')
    class Meta:
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Hệ thống Thông báo'

# 13. Bảng CHAT_ROOMS
class ChatRoom(TimeStampedModel):
    name = models.CharField(max_length=150)
    is_private = models.BooleanField(default=False)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_rooms')
    class Meta:
        verbose_name = 'Phòng Chat'
        verbose_name_plural = 'Danh sách Phòng Chat'

# 14. Bảng CHATS
class Chat(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats')
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='chats')
    message = models.TextField()
    class Meta:
        verbose_name = 'Tin nhắn Chat'
        verbose_name_plural = 'Lịch sử Tin nhắn'

class Event(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tên sự kiện")
    cover_image = models.ImageField(upload_to='events/covers/', null=True, blank=True, verbose_name="Ảnh bìa")
    content = models.TextField(verbose_name="Nội dung chi tiết")
    start_date = models.DateTimeField(verbose_name="Thời gian bắt đầu")
    end_date = models.DateTimeField(verbose_name="Thời gian kết thúc")
    location = models.CharField(max_length=255, verbose_name="Địa điểm tổ chức")
    max_participants = models.PositiveIntegerField(default=100, verbose_name="Giới hạn người tham gia (0 = Không giới hạn)")
    is_active = models.BooleanField(default=True, verbose_name="Đang mở")
    created_at = models.DateTimeField(auto_now_add=True)

    def get_cover(self):
        """Trả về URL ảnh bìa hoặc ảnh mặc định nếu không có"""
        if self.cover_image and hasattr(self.cover_image, 'url'):
            return self.cover_image.url
        return "https://placehold.co/150x150?text=Event"

    def __str__(self):
        return self.title

    def registered_count(self):
        return self.eventregistration_set.count()
        
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Sự kiện"
        verbose_name_plural = "Danh sách Sự kiện"

class EventRegistration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

    class Meta:
        unique_together = ('user', 'event') # Khôi phục lại chốt chặn chống đăng ký trùng
        verbose_name = "Đăng ký sự kiện"
        verbose_name_plural = "Danh sách Đăng ký Sự kiện"

# core/models.py
@receiver(post_save, sender=Book)
def notify_new_book(sender, instance, created, **kwargs):
    if created:
        users = User.objects.all()
        
        # SỬA TẠI ĐÂY: Đổi 'id' thành 'book_id' để khớp với urls.py
        book_url = reverse('book_detail', kwargs={'book_id': instance.id})
        
        link_html = f"<a href='{book_url}' class='fw-bold text-primary'>Khám phá ngay!</a>"
        message_text = f"🔥🔥🔥 Sách mới lên kệ: Thư viện vừa bổ sung cuốn '{instance.title}'. {link_html}"
        
        notifications = [
            Notification(
                user=u, 
                message=message_text,
                type='SYSTEM',
                status='UNREAD'
            ) for u in users
        ]
        Notification.objects.bulk_create(notifications)

# Chat Model - Lưu lịch sử chat
class ChatMessage(TimeStampedModel):
    ROLE_CHOICES = (
        ('USER', 'User'),
        ('BOT', 'Bot'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message = models.TextField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    
    class Meta:
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"