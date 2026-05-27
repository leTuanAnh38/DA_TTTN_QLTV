from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
# Import 6 file view riêng biệt từ thư mục core/views/ mà chúng ta vừa tạo
from core.views import (
    api_staff,
    auth_views,
    book_views,
    borrow_views,
    user_views,
    staff_views,
    api_views
)
from core.views.api_views import RegisterView
from core.views.chat_views import chat_message_api, get_chat_history, get_chat_greeting
from core.views.admin_dashboard import AdminDashboardView, admin_chart_api

urlpatterns = [
    # ==========================================
    # 1. NHÓM XÁC THỰC (AUTHENTICATION)
    # ==========================================
    path('login/', auth_views.user_login, name='login'),
    path('register/', auth_views.register, name='register'),
    path('logout/', auth_views.user_logout, name='logout'),
    path('change-password/', auth_views.change_password, name='change_password'),

    # ==========================================
    # 2. NHÓM HIỂN THỊ SÁCH (TRANG CHỦ & TÌM KIẾM)
    # ==========================================
    path('', book_views.home, name='home'),
    path('books/', book_views.book_list, name='book_list'),
    path('premium-books/', book_views.premium_book_list, name='premium_books'),
    path('book/<int:book_id>/', book_views.book_detail, name='book_detail'),
    path('book/<int:book_id>/review/', book_views.add_review, name='add_review'),
    path('guide/', book_views.guide_view, name='guide'),
    path('contact/', book_views.contact_view, name='contact'),

    # ==========================================
    # 3. NHÓM NGƯỜI DÙNG CÁ NHÂN (USER PROFILE)
    # ==========================================
    path('profile/', user_views.profile_view, name='profile'),
    path('profile/reviews/', user_views.my_reviews_view, name='my_reviews'),
    path('pay-penalties/', user_views.pay_all_penalties, name='pay_all_penalties'),
    path('wishlist/', user_views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:book_id>/', user_views.toggle_wishlist, name='toggle_wishlist'),
    path('notifications/', user_views.notification_list, name='notification_list'),
    # URL cho trang danh sách Sự kiện
    path('events/', book_views.event_list, name='event_list'),
    
    # URL API cho nút bấm Tham gia/Hủy tham gia
    path('api/events/<int:event_id>/toggle/', api_views.api_toggle_event_registration, name='api_toggle_event_registration'),

    # ==========================================
    # 4. NHÓM MƯỢN TRẢ SÁCH (BORROW / RETURN)
    # ==========================================
    # URL Giỏ sách mới
    path('cart/', borrow_views.view_cart, name='view_cart'),
    path('api/cart/add/<int:book_id>/', borrow_views.add_to_cart, name='api_add_to_cart'),
    path('cart/remove/<int:book_id>/', borrow_views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', borrow_views.checkout_cart, name='checkout_cart'),
    # xử lý mượn trả gia hạn sách
    path('borrow/<int:book_id>/', borrow_views.borrow_book, name='borrow_book'),
    path('borrow-history/', borrow_views.borrow_history, name='borrow_history'),
    path('return/<int:transaction_id>/', borrow_views.return_book, name='return_book'),
    path('return-batch/', borrow_views.return_books_batch, name='return_books_batch'),
    path('renew/<int:transaction_id>/', borrow_views.renew_book, name='renew_book'),

    # ==========================================
    # 5. NHÓM NGHIỆP VỤ THỦ THƯ (STAFF DASHBOARD)
    # ==========================================
    path('staff/', staff_views.staff_dashboard, name='staff_dashboard'),
    path('staff/books/', staff_views.staff_book_list, name='staff_book_list'),
    path('staff/book/add/', staff_views.add_book, name='add_book'),
    path('staff/book/edit/<int:book_id>/', staff_views.edit_book, name='edit_book'),
    path('staff/book/delete/<int:book_id>/', staff_views.delete_book, name='delete_book'),
    
    path('staff/borrows/', staff_views.staff_borrow_management, name='staff_borrow_management'),
    path('staff/borrows/approve/<int:transaction_id>/', staff_views.staff_approve_borrow, name='staff_approve_borrow'),
    path('staff/borrows/confirm-return/<int:transaction_id>/', staff_views.staff_confirm_return, name='staff_confirm_return'),
    
    path('staff/penalties/', staff_views.staff_penalty_management, name='staff_penalty_management'),
    path('staff/penalties/confirm/<int:penalty_id>/', staff_views.staff_confirm_penalty, name='staff_confirm_penalty'),
    
    path('staff/users/', staff_views.staff_user_management, name='staff_user_management'),
    path('staff/users/<int:user_id>/', staff_views.staff_user_detail, name='staff_user_detail'),
    # --- QUẢN LÝ DANH MỤC (CATEGORY) ---
    path('staff/categories/', staff_views.staff_category_list, name='staff_category_list'),
    path('staff/categories/add/', staff_views.staff_category_form, name='staff_category_add'),
    path('staff/categories/edit/<int:pk>/', staff_views.staff_category_form, name='staff_category_edit'),
    path('staff/categories/delete/<int:pk>/', staff_views.staff_category_delete, name='staff_category_delete'),

    # --- QUẢN LÝ NHÀ XUẤT BẢN (PUBLISHER) ---
    path('staff/publishers/', staff_views.staff_publisher_list, name='staff_publisher_list'),
    path('staff/publishers/add/', staff_views.staff_publisher_form, name='staff_publisher_add'),
    path('staff/publishers/edit/<int:pk>/', staff_views.staff_publisher_form, name='staff_publisher_edit'),
    path('staff/publishers/delete/<int:pk>/', staff_views.staff_publisher_delete, name='staff_publisher_delete'),

    path('staff/reviews/', staff_views.staff_review_management, name='staff_review_management'),
    # ==========================================
    # QUẢN LÝ SỰ KIỆN DÀNH CHO THỦ THƯ
    # ==========================================
    path('staff/events/', staff_views.staff_event_list, name='staff_event_list'),
    path('staff/events/add/', staff_views.event_create, name='event_create'),
    path('staff/events/<int:event_id>/edit/', staff_views.event_edit, name='event_edit'),
    path('staff/events/<int:event_id>/delete/', staff_views.event_delete, name='event_delete'),
    # ==========================================
    # 6. NHÓM API (XỬ LÝ NGẦM AJAX & LOAD MORE)
    # ==========================================
    path('api/books/', api_views.api_get_books, name='api_get_books'),
    path('api/books/add/', api_views.api_create_book, name='api_create_book'),
    path('api/books/delete/<int:book_id>/', api_views.api_delete_book, name='api_delete_book'),
    
    path('api/chart-data/', api_views.admin_chart_data, name='admin_chart_data'),
    path('api/search/', api_views.live_search_api, name='api_live_search'),
    path('api/wishlist/toggle/<int:book_id>/', api_views.toggle_wishlist_api, name='api_toggle_wishlist'),
    path('api/review/add/<int:book_id>/', api_views.api_add_review, name='api_add_review'),
    path('api/admin-chart/', api_views.admin_chart_data, name='admin_chart_data'),
    
    path('api/books/load-more/', api_views.api_load_more_books, name='api_load_more_books'),
    path('api/notifications/load-more/', api_views.api_load_more_notifications, name='api_load_more_notifications'),
    path('api/history/load-more/', api_views.api_load_more_history, name='api_load_more_history'),
    path('api/wishlist/load-more/', api_views.api_load_more_wishlist, name='api_load_more_wishlist'),
    path('api/notifications/unread-count/', api_views.api_unread_notification_count, name='api_unread_notification_count'),
    # Thêm URL cho Bàn làm việc Admin (Khớp với SIMPLEUI_INDEX trong settings.py)
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('api/admin-chart/', admin_chart_api, name='admin_chart_api'),

    #path('login/', auth_views.user_login(template_name='core/login.html'), name='login'),


    # 1. API Đăng ký tài khoản
    path('api/register/', RegisterView.as_view(), name='api_register'),
    
    # 2. API Đăng nhập (Lấy thẻ Access & Refresh)
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # 3. API Xin cấp lại thẻ Access mới (khi thẻ cũ hết hạn)
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 4. API Chat với Gemini
    path('api/chat/', chat_message_api, name='chat_api'),
    path('api/chat/history/', get_chat_history, name='chat_history'),
    path('api/chat/greeting/', get_chat_greeting, name='chat_greeting'),

    path('api/staff/books/load-more/', api_staff.api_staff_load_more_books, name='api_staff_load_more_books'),
    path('api/staff/borrows/load-more/', api_staff.api_staff_load_more_borrows, name='api_staff_load_more_borrows'),
    path('api/staff/reviews/<int:book_id>/', api_staff.api_staff_get_book_reviews, name='api_staff_get_book_reviews'),
]