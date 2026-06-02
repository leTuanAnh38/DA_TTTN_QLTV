# file: core/views/user_views.py

import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum

# Import models từ app core
from core.models import Book, Wishlist, BorrowTransaction, Notification, Review, Penalty

# ==========================================
# 1. HỒ SƠ CÁ NHÂN & THANH TOÁN PHẠT
# ==========================================

@login_required(login_url='login')
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        
        # 1. Lấy dữ liệu và dùng .strip() để xóa khoảng trắng thừa ở 2 đầu
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        msv = (request.POST.get('msv') or '').strip()
        lop = (request.POST.get('lop') or '').strip()
        dia_chi = (request.POST.get('dia_chi') or '').strip()
        
        # YÊU CẦU 3: VALIDATION DỮ LIỆU ĐẦU VÀO
        errors = []
        
        # Kiểm tra MSV: Chỉ được chứa chữ cái, số và độ dài từ 5-15 ký tự
        if msv and not re.match(r'^[A-Za-z0-9]{5,15}$', msv):
            errors.append("Mã sinh viên không hợp lệ (Chỉ chứa chữ/số, dài từ 5 đến 15 ký tự).")
            
        # Kiểm tra Tên: Không được phép chứa số
        if (first_name and re.search(r'\d', first_name)) or (last_name and re.search(r'\d', last_name)):
            errors.append("Họ và tên đệm không được phép chứa chữ số.")
            
        # Kiểm tra Lớp: Không được chứa các ký tự đặc biệt nguy hiểm (Phòng chống XSS)
        if lop and re.search(r'[<>{}\[\];]', lop):
            errors.append("Tên lớp chứa ký tự không hợp lệ.")
            
        # Kiểm tra file Avatar (nếu có upload)
        if 'avatar' in request.FILES:
            avatar_file = request.FILES['avatar']
            if not avatar_file.content_type.startswith('image/'):
                errors.append("File tải lên không phải là định dạng hình ảnh hợp lệ.")
                
        # NẾU CÓ LỖI: Báo lỗi ra màn hình và dừng lại, KHÔNG lưu vào Database
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('profile')
        
        # 2. VƯỢT QUA KIỂM TRA: Bắt đầu lưu dữ liệu
        user.first_name = first_name
        user.last_name = last_name
        user.msv = msv
        user.lop = lop
        user.dia_chi = dia_chi
        
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
            
        user.save()
        messages.success(request, 'Cập nhật hồ sơ thành công!')
        return redirect('profile')
        
    # XỬ LÝ KHI TRUY CẬP TRANG (GET REQUEST)
    all_reviews = Review.objects.filter(user=request.user).select_related('book').order_by('-created_at')
    user_reviews = all_reviews[:3] # Chỉ lấy 3 cái mới nhất
    has_more_reviews = all_reviews.count() > 3
    
    # KIỂM TRA TRẠNG THÁI TIỀN PHẠT ĐỂ HIỂN THỊ NÚT
    has_unpaid = Penalty.objects.filter(user=request.user, status='UNPAID').exists()
    
    processing_penalties = Penalty.objects.filter(user=request.user, status='PROCESSING')
    has_processing = processing_penalties.exists()
    
    # Tính tổng tiền đang chờ duyệt (nếu có)
    processing_amount = processing_penalties.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return render(request, 'core/user/profile.html', {
        'user_reviews': user_reviews,
        'has_more_reviews': has_more_reviews,
        'has_unpaid': has_unpaid,
        'has_processing': has_processing,
        'processing_amount': processing_amount 
    })

@login_required(login_url='login')
def my_reviews_view(request):
    reviews_list = Review.objects.filter(user=request.user).select_related('book').order_by('-created_at')
    
    paginator = Paginator(reviews_list, 10) 
    page = request.GET.get('page', 1)
    
    try:
        reviews = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        reviews = paginator.page(1)
        
    return render(request, 'core/user/my_reviews.html', {
        'reviews': reviews
    })
    
@login_required(login_url='login')
def pay_all_penalties(request):
    if request.method == 'POST':
        method = request.POST.get('payment_method', '').strip()
        valid_methods = dict(Penalty.PAYMENT_METHODS).keys()
        
        # VALIDATION: Kiểm tra phương thức thanh toán
        if method not in valid_methods:
            messages.error(request, "Phương thức thanh toán không hợp lệ. Vui lòng thử lại!")
            return redirect('profile')

        unpaid_penalties = Penalty.objects.filter(user=request.user, status='UNPAID')
        
        if unpaid_penalties.exists():
            unpaid_penalties.update(payment_method=method, status='PROCESSING')
            messages.success(request, f"Đã gửi yêu cầu thanh toán bằng hình thức: {dict(Penalty.PAYMENT_METHODS).get(method)}.")
        else:
            messages.info(request, "Bạn hiện không có khoản phạt nào cần thanh toán.")
            
        return redirect('profile')

# ==========================================
# 2. DANH SÁCH YÊU THÍCH (WISHLIST)
# ==========================================

@login_required(login_url='login')
def toggle_wishlist(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, book=book).first()
    
    if wishlist_item:
        wishlist_item.delete()
        messages.success(request, f"Đã bỏ '{book.title}' khỏi danh sách yêu thích.")
    else:
        Wishlist.objects.create(user=request.user, book=book)
        messages.success(request, f"Đã thêm '{book.title}' vào danh sách yêu thích.")
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required(login_url='login')
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).order_by('-created_at')
    
    paginator = Paginator(wishlist_items, 6) 
    page = request.GET.get('page', 1)
    try:
        items = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        items = paginator.page(1)
        
    borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
    pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)
    
    return render(request, 'core/user/wishlist.html', {
        'wishlist_items': items, 
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids)
    })

# ==========================================
# 3. THÔNG BÁO (NOTIFICATIONS)
# ==========================================

@login_required(login_url='login')
def notification_list(request):
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifications_list, 8) 
    page = request.GET.get('page', 1)
    
    try:
        notifications = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        notifications = paginator.page(1)
        
    # Đánh dấu đã đọc những thông báo hiện ra
    if notifications:
        Notification.objects.filter(id__in=[n.id for n in notifications], status='UNREAD').update(status='READ')
    
    return render(request, 'core/user/notifications.html', {'notifications': notifications})