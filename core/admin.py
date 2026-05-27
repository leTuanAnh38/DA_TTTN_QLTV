from django.contrib import admin
from django.utils.html import format_html
from .models import (
    User, Category, Publisher, Book, BookImage, 
    BorrowTransaction, Penalty, Review, Wishlist, 
    Recommendation, Membership, Notification, ChatRoom, Chat
)
from .models import Event, EventRegistration

# 1. Quản lý Người dùng (Dựa trên bảng USERS)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'membership_level', 'is_staff')
    list_filter = ('role', 'membership_level', 'is_staff')
    search_fields = ('username', 'email', 'phone')

# 2. Quản lý Sách (Dựa trên bảng BOOKS)
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    # display_cover là hàm hiển thị ảnh bìa nhỏ
    list_display = ('display_cover', 'title', 'author', 'category', 'quantity', 'status')
    list_editable = ('quantity', 'status')
    list_filter = ('category', 'status', 'published_year')
    search_fields = ('title', 'author')
    list_per_page = 20

    def display_cover(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="width: 45px; height: 60px; border-radius: 4px; object-fit: cover;" />', obj.cover_image)
        return "N/A"
    display_cover.short_description = 'Bìa'

# 3. Quản lý Giao dịch mượn (Dựa trên bảng BORROW_TRANSACTIONS)
@admin.register(BorrowTransaction)
class BorrowTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'borrow_date', 'due_date', 'status')
    list_filter = ('status', 'borrow_date')
    search_fields = ('user__username', 'book__title')
    date_hierarchy = 'borrow_date'

# 4. Quản lý Xử phạt (Dựa trên bảng PENALTIES - ĐÃ SỬA LỖI KHANH GẶP)
@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    # Phải dùng đúng các tên trường: user, borrow_transaction, amount, due_date
    list_display = ('user', 'borrow_transaction', 'amount', 'due_date')
    list_filter = ('due_date',)
    search_fields = ('user__username', 'reason')
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'location', 'max_participants', 'is_active')
    list_filter = ('is_active', 'start_date')
    search_fields = ('title', 'location')

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'registered_at')
    list_filter = ('event',)
    search_fields = ('user__username', 'event__title')
# 5. Quản lý Nhận xét (Dựa trên bảng REVIEWS)
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'rating', 'created_at')
    list_filter = ('rating',)

# 6. Quản lý Thông báo (Dựa trên bảng NOTIFICATIONS)
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'status', 'created_at')
    list_filter = ('type', 'status')

# 7. Đăng ký nhanh các bảng còn lại
admin.site.register(Category)
admin.site.register(Publisher)
#admin.site.register(BookImage)
admin.site.register(Wishlist)
admin.site.register(Recommendation)
admin.site.register(Membership)
admin.site.register(ChatRoom)
admin.site.register(Chat)