# file: core/views/staff_views.py
from sched import Event
from django.db.models import Case, When, Value, IntegerField
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum
from django.db import transaction as db_transaction
from ..models import Category, Publisher, Review
from ..forms import CategoryForm, PublisherForm
from django.core.paginator import Paginator
from core.models import Book, BorrowTransaction, Penalty, User, Notification
from core.forms import BookForm
from django.db.models import Avg, Count, OuterRef, Subquery
from django.urls import reverse
from urllib.parse import urlencode
from datetime import datetime
from ..models import Event
from ..forms import EventForm
# Hàm kiểm tra quyền Staff
def is_staff(user):
    return user.is_authenticated and user.role in ['STAFF', 'ADMIN']
# ==========================================
# 1. QUẢN LÝ KHO SÁCH (CRUD)
# ==========================================
@user_passes_test(is_staff, login_url='login')
def staff_dashboard(request):
    # 1. Lấy đơn trễ hạn
    overdue_transactions = BorrowTransaction.objects.filter(
        status='OVERDUE'
    ).select_related('user', 'book').order_by('due_date') 

    # 2. Lấy đơn CHỜ DUYỆT MƯỢN (Mới thêm)
    pending_transactions = BorrowTransaction.objects.filter(
        status='PENDING'
    ).select_related('user', 'book').order_by('created_at')
    
    # 3. Lấy đơn ĐANG MƯỢN / CHỜ TRẢ (Mới thêm)
    borrowed_transactions = BorrowTransaction.objects.filter(
        status='BORROWED'
    ).select_related('user', 'book').order_by('due_date')

    total_library_books = Book.objects.aggregate(total=Sum('initial_quantity'))['total'] or 0
    current_available_books = Book.objects.aggregate(total=Sum('quantity'))['total'] or 0

    return render(request, 'core/staff/dashboard.html', {
        'overdue_transactions': overdue_transactions,
        'pending_transactions': pending_transactions,  # Truyền dữ liệu ra template
        'borrowed_transactions': borrowed_transactions, # Truyền dữ liệu ra template
        'total_library_books': total_library_books,
        'current_available_books': current_available_books
    })

@user_passes_test(is_staff, login_url='login')
def staff_book_list(request):
    query = request.GET.get('search_staff', '')
    books = Book.objects.all() 

    # 1. Xử lý tìm kiếm
    if query:
        books = books.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) |
            Q(location__icontains=query) 
        )

    # 2. Xử lý sắp xếp
    sort_by = request.GET.get('sort_by', 'newest')
    if sort_by == 'stock_desc':
        books = books.order_by('-quantity', '-created_at')
    elif sort_by == 'stock_asc':
        books = books.order_by('quantity', '-created_at')
    else: # newest
        books = books.order_by('-created_at')

    # 3. Tính toán thống kê
    total_books_count = books.count() # Số lượng đầu sách (sau khi filter)
    total_physical_books = books.aggregate(total=Sum('initial_quantity'))['total'] or 0

    # 4. Phân trang
    page_number = request.GET.get('page', 1) 
    paginator = Paginator(books, 10) 
    page_obj = paginator.get_page(page_number) 

    return render(request, 'core/staff/book_list.html', {
        'books': page_obj,
        'query': query,
        'sort_by': sort_by,
        'total_books_count': total_books_count,
        'total_physical_books': total_physical_books
    })
@user_passes_test(is_staff)
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, f"Thêm sách '{form.cleaned_data.get('title')}' thành công!")
            return redirect('staff_book_list')
    else:
        form = BookForm()
    
    return render(request, 'core/staff/book_form.html', {
        'form': form, 
        'title': 'Thêm sách mới'
    })

@user_passes_test(is_staff)
def edit_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # 1. Bắt lấy số trang hiện tại từ URL (Nếu không có thì mặc định là 1)
    current_page = request.GET.get('page', '1')
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật thông tin sách thành công!")
            
            # 2. Tạo URL chuyển hướng về Kho sách kèm theo số trang hiện tại
            base_url = reverse('staff_book_list')
            query_string = urlencode({'page': current_page})
            url = f"{base_url}?{query_string}"
            return redirect(url)
    else:
        form = BookForm(instance=book)
        
    return render(request, 'core/staff/book_form.html', {
        'form': form, 
        'title': 'Chỉnh sửa sách',
        'current_page': current_page  # 3. Truyền số trang ra giao diện HTML cho nút Hủy bỏ
    })

@user_passes_test(is_staff)
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # 1. Lấy số trang hiện tại từ URL
    current_page = request.GET.get('page', '1')
    
    # 2. Xóa sách
    book.delete()
    messages.success(request, "Đã xóa sách khỏi hệ thống!")
    
    # 3. Trở về đúng trang vừa thao tác xóa
    base_url = reverse('staff_book_list')
    query_string = urlencode({'page': current_page})
    url = f"{base_url}?{query_string}"
    return redirect(url)

# --- QUẢN LÝ DANH MỤC ---
@user_passes_test(is_staff, login_url='login')
def staff_category_list(request):
    # 1. Bắt từ khóa tìm kiếm
    query = request.GET.get('search_query', '').strip()
    
    # 2. Lấy danh sách danh mục (Sắp xếp theo tên như cũ)
    categories = Category.objects.all().order_by('name')
    
    # 3. Xử lý bộ lọc tìm kiếm
    if query:
        categories = categories.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
        
    # 4. Xử lý phân trang (10 danh mục / trang)
    page_number = request.GET.get('page', 1)
    paginator = Paginator(categories, 10)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/staff/category_list.html', {
        'categories': page_obj,  # Truyền danh sách đã phân trang ra HTML
        'query': query,           # Truyền lại biến q để giữ text trên thanh tìm kiếm
        'total_categories': Category.objects.count()
    })

def staff_category_form(request, pk=None):
    instance = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật danh mục thành công!")
            return redirect('staff_category_list')
    else:
        form = CategoryForm(instance=instance)
    
    title = "Chỉnh sửa danh mục" if pk else "Thêm danh mục mới"
    return render(request, 'core/staff/category_form.html', {'form': form, 'title': title})

@user_passes_test(is_staff, login_url='login')
def staff_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f"Đã xóa danh mục '{name}' thành công!")
    return redirect('staff_category_list')

# --- QUẢN LÝ NHÀ XUẤT BẢN ---
@user_passes_test(is_staff, login_url='login')
def staff_publisher_list(request):
    # 1. Bắt từ khóa tìm kiếm trên URL
    query = request.GET.get('search_query', '').strip()
    
    # 2. Lấy toàn bộ danh sách NXB (Sắp xếp theo tên như code cũ của bạn)
    publishers = Publisher.objects.all().order_by('name')
    
    # 3. Lọc dữ liệu nếu admin có gõ tìm kiếm
    if query:
        publishers = publishers.filter(
            Q(name__icontains=query) |
            Q(address__icontains=query)
        ).distinct()
        
    # 4. Chia trang (10 nhà xuất bản / 1 trang)
    page_number = request.GET.get('page', 1)
    paginator = Paginator(publishers, 10)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/staff/publisher_list.html', {
        'publishers': page_obj, 
        'query': query,          
        'total_publishers': Publisher.objects.count()
    })

def staff_publisher_form(request, pk=None):
    instance = get_object_or_404(Publisher, pk=pk) if pk else None
    if request.method == 'POST':
        form = PublisherForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật nhà xuất bản thành công!")
            return redirect('staff_publisher_list')
    else:
        form = PublisherForm(instance=instance)
    
    title = "Chỉnh sửa nhà xuất bản" if pk else "Thêm nhà xuất bản mới"
    return render(request, 'core/staff/category_form.html', {'form': form, 'title': title})

@user_passes_test(is_staff, login_url='login')
def staff_publisher_delete(request, pk):
    publisher = get_object_or_404(Publisher, pk=pk)
    name = publisher.name
    publisher.delete()
    messages.success(request, f"Đã xóa nhà xuất bản '{name}' thành công!")
    return redirect('staff_publisher_list')

@user_passes_test(is_staff, login_url='login')
def staff_borrow_management(request):
    today_date = timezone.now().date()
    query = request.GET.get('search_query', '').strip()
    status_filter = request.GET.get('status', '')
    # LẤY DANH SÁCH GIAO DỊCH & XỬ LÝ TÌM KIẾM
    transactions = BorrowTransaction.objects.select_related('user', 'book').annotate(
        status_priority=Case(
            When(status='PENDING', reason='YÊU CẦU TRẢ', then=Value(1)), 
            When(status='PENDING', then=Value(2)),                     
            When(status='OVERDUE', then=Value(3)),
            When(status='BORROWED', then=Value(4)),
            When(status='CANCELLED', then=Value(5)),
            When(status='RETURNED', then=Value(6)),
            default=Value(7),
            output_field=IntegerField(),
        )
    )

    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    if query:
        transactions = transactions.filter(
            Q(user__msv__icontains=query) |          
            Q(user__username__icontains=query) |     
            Q(book__title__icontains=query)
        ).distinct()
        
    transactions = transactions.order_by('status_priority', '-updated_at')
    # PHÂN TRANG & TÍNH TOÁN DỮ LIỆU PHỤ TRỢ
    page_number = request.GET.get('page', 1) 
    paginator = Paginator(transactions, 10)
    page_obj = paginator.get_page(page_number) 

    # Tính toán số ngày đến sớm cho các đơn chờ lấy
    for trans in page_obj:
        if trans.status == 'PENDING' and trans.pickup_date and trans.pickup_date > today_date:
            trans.days_early = (trans.pickup_date - today_date).days
        else:
            trans.days_early = 0
    
    return render(request, 'core/staff/borrow_management.html', {
        'transactions': page_obj, 
        'query': query,
        'status_filter': status_filter,
        'today': today_date
    })
# Xác nhận duyệt đơn mượn sách của sinh viên (Cả sách Free và có phí)
@user_passes_test(is_staff, login_url='login')
def staff_approve_borrow(request, transaction_id):
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, status='PENDING')
    
    try:
        with db_transaction.atomic():
            borrow_record.status = 'BORROWED'
            borrow_record.is_paid = True  
            borrow_record.borrow_date = timezone.now().date()
            borrow_record.due_date = timezone.now().date() + timedelta(days=14)
            borrow_record.save() 
            #Phân loại sách để hiển thị tin nhắn phù hợp
            is_premium = borrow_record.book.price and borrow_record.book.price > 0
            
            if is_premium:
                msg_noti = f"Thủ thư đã duyệt tiền và giao cuốn sách có phí '{borrow_record.book.title}' cho bạn. Hạn trả là {borrow_record.due_date.strftime('%d/%m/%Y')}."
                msg_success = f"Đã xác nhận thu tiền và giao sách có phí cho sinh viên {borrow_record.user.msv}."
            else:
                msg_noti = f"Thủ thư đã duyệt và giao cuốn sách '{borrow_record.book.title}' cho bạn. Hạn trả là {borrow_record.due_date.strftime('%d/%m/%Y')}."
                msg_success = f"Đã xác nhận duyệt giao sách cho sinh viên {borrow_record.user.msv}."

            Notification.objects.create(
                user=borrow_record.user,
                message=msg_noti,
                type='SYSTEM',
                status='UNREAD'
            )
            
        messages.success(request, msg_success)
    except Exception as e:
        messages.error(request, f"Lỗi hệ thống: {str(e)}")
        
    return redirect('staff_borrow_management')
# xác nh thu tiền phạt và hoàn tất yêu cầu trả sách của sinh viên
@user_passes_test(is_staff, login_url='login')
def staff_confirm_return(request, transaction_id):
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, status__in=['BORROWED', 'PENDING', 'OVERDUE'])
    user = borrow_record.user
    
    if request.method == 'POST':
        book_condition = request.POST.get('book_condition', 'NORMAL')
        # ---> Lấy giá trị ô tick từ HTML
        pay_now = request.POST.get('pay_now') == 'YES'
        
        try:
            with db_transaction.atomic():
                today = timezone.now().date()
                borrow_record.status = 'RETURNED'
                borrow_record.return_date = today
                borrow_record.save()
                
                fine_amount = 0
                penalty_reasons = []
                
                # 1. Xử lý phạt trễ hạn
                if today > borrow_record.due_date:
                    user.points = max(0, user.points - 5)
                    days_late = (today - borrow_record.due_date).days
                    late_fine = days_late * 5000
                    fine_amount += late_fine
                    penalty_reasons.append(f"Trả trễ {days_late} ngày ({late_fine:,.0f}đ)")
                else:
                    user.points += 10 
                    
                # 2. Xử lý phạt hư hỏng/mất sách
                original_price = borrow_record.book.original_price or 0
                if book_condition == 'LIGHT_DAMAGE':
                    damage_fine = int(float(original_price) * 0.10) 
                    fine_amount += damage_fine
                    penalty_reasons.append(f"Hư hỏng nhẹ sách ({damage_fine:,.0f}đ)")
                elif book_condition == 'LOST_OR_DESTROYED':
                    damage_fine = int(original_price) 
                    fine_amount += damage_fine
                    penalty_reasons.append(f"Mất/Hư hỏng nặng sách ({damage_fine:,.0f}đ)")
                    
                # 3. Tạo phiếu phạt và thông báo
                if fine_amount > 0:
                    reason_str = " + ".join(penalty_reasons)
                    
                    # ---> NẾU THỦ THƯ TICK ĐÃ THU TIỀN: Lưu status là PAID luôn
                    penalty_status = 'PAID' if pay_now else 'UNPAID'
                    
                    Penalty.objects.create(
                        user=user,
                        borrow_transaction=borrow_record,
                        amount=fine_amount,
                        reason=reason_str,
                        status=penalty_status
                    )
                    
                    if pay_now:
                        msg_noti = f"Thủ thư đã thu hồi cuốn '{borrow_record.book.title}'. Hệ thống ghi nhận bạn đã nộp trực tiếp {fine_amount:,.0f} VNĐ cho khoản phạt ({reason_str})."
                    else:
                        msg_noti = f"CẢNH BÁO: Thủ thư đã thu hồi cuốn '{borrow_record.book.title}'. Bạn bị phạt {fine_amount:,.0f} VNĐ ({reason_str}). Vui lòng vào Hồ sơ để thanh toán sau."
                        
                    Notification.objects.create(user=user, message=msg_noti, type='SYSTEM', status='UNREAD')
                else:
                    Notification.objects.create(
                        user=user,
                        message=f"Tuyệt vời! Thủ thư đã thu hồi cuốn '{borrow_record.book.title}' thành công. Bạn được cộng 10 điểm thưởng vì trả đúng hạn và giữ sách tốt.",
                        type='SYSTEM',
                        status='UNREAD'
                    )
                
                user.save() 
                
                # 4. Hoàn sách vào kho (Trừ khi bị mất)
                book = borrow_record.book
                if book_condition != 'LOST_OR_DESTROYED':
                    book.quantity += 1
                book.save()
                
                messages.success(request, f"Đã thu hồi sách từ Sinh viên {user.msv}. Tình trạng: {book_condition}. {'(ĐÃ THU XONG TIỀN PHẠT)' if fine_amount > 0 and pay_now else ''}")
        except Exception as e:
            messages.error(request, f"Lỗi hệ thống: {str(e)}")
            
    return redirect('staff_borrow_management')
# ==========================================
# 3. QUẢN LÝ TIỀN PHẠT & NGƯỜI DÙNG
# ==========================================

@user_passes_test(is_staff, login_url='login')
def staff_penalty_management(request):
    query = request.GET.get('search_query', '').strip()
    
    # 1. Lấy TẤT CẢ khoản phạt
    penalties = Penalty.objects.select_related('user').annotate(
        status_priority=Case(
            When(status='PROCESSING', then=Value(1)), 
            When(status='UNPAID', then=Value(2)),
            When(status='PAID', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    )
    
    # 2. Xử lý tìm kiếm theo thanh search
    if query:
        penalties = penalties.filter(
            Q(user__msv__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query)
        ).distinct()

    penalties = penalties.order_by('status_priority', '-created_at')

    # 4. Tính toán thống kê tổng quát
    total_pending_fines = Penalty.objects.filter(status__in=['UNPAID', 'PROCESSING']).aggregate(total=Sum('amount'))['total'] or 0
    total_penalty_count = Penalty.objects.count()
    total_collected_amount = Penalty.objects.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or 0

    # 5. Phân trang (10 giao dịch / trang)
    page_number = request.GET.get('page', 1) 
    paginator = Paginator(penalties, 10)
    page_obj = paginator.get_page(page_number) 
    
    return render(request, 'core/staff/penalty_management.html', {
        'penalties': page_obj,  
        'query': query,
        'total_pending_fines': total_pending_fines,
        'total_penalty_count': total_penalty_count,
        'total_collected_amount': total_collected_amount
    })

@user_passes_test(is_staff, login_url='login')
def staff_confirm_penalty(request, penalty_id):
    penalty = get_object_or_404(Penalty, id=penalty_id, status__in=['UNPAID', 'PROCESSING'])
    penalty.status = 'PAID'
    penalty.save()
    
    Notification.objects.create(
        user=penalty.user,
        message=f"Thủ thư đã xác nhận thu khoản tiền phạt {penalty.amount} VNĐ của bạn. Cảm ơn bạn đã hoàn tất nghĩa vụ!",
        type='SYSTEM',
        status='UNREAD'
    )
    
    messages.success(request, f"Đã xác nhận thu tiền phạt thành công từ sinh viên {penalty.user.msv}.")
    return redirect('staff_penalty_management')

@user_passes_test(is_staff, login_url='login')
def staff_user_management(request):
    # 1. Lọc danh sách người đọc (Rất tốt, đã loại trừ đúng Admin/Staff)
    readers = User.objects.filter(
        is_staff=False, 
        is_superuser=False
    ).exclude(role__in=['STAFF', 'ADMIN']).order_by('username')
    
    # 2. Xử lý tìm kiếm
    query = request.GET.get('search_query', '').strip()
    if query:
        readers = readers.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(msv__icontains=query)
        )
        
    page_number = request.GET.get('page', 1)  
    paginator = Paginator(readers, 10)       
    page_obj = paginator.get_page(page_number) 
    
    return render(request, 'core/staff/user_management.html', {
        'readers': page_obj,  
        'total_readers': readers.count() 
    })

@user_passes_test(is_staff, login_url='login')
def staff_user_detail(request, user_id):
    reader = get_object_or_404(User, id=user_id)
    borrow_history = BorrowTransaction.objects.filter(user=reader).order_by('-created_at')
    penalties = Penalty.objects.filter(user=reader).order_by('-created_at')
    
    return render(request, 'core/staff/user_detail.html', {
        'reader': reader,
        'borrow_history': borrow_history,
        'penalties': penalties
    })

@user_passes_test(is_staff, login_url='login')
def staff_review_management(request):
    # 1. Bắt từ khóa tìm kiếm
    query = request.GET.get('search_query', '').strip()

    # Lấy thông tin bài đánh giá gần nhất của mỗi cuốn sách
    latest_review = Review.objects.filter(book=OuterRef('pk')).order_by('-created_at')

    books = Book.objects.annotate(
        review_count=Count('reviews'), 
        avg_rating=Avg('reviews__rating'), 
        latest_reviewer=Subquery(latest_review.values('user__username')[:1]),
        latest_review_date=Subquery(latest_review.values('created_at')[:1])
    ).filter(review_count__gt=0)
    
    # 2. Xử lý tìm kiếm (nếu có)
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query)
        )

    # 3. Sắp xếp dữ liệu
    books = books.order_by('-avg_rating', '-review_count')

    # 4. Xử lý phân trang (10 cuốn / 1 trang)
    page_number = request.GET.get('page', 1)
    paginator = Paginator(books, 10)
    page_obj = paginator.get_page(page_number)

    # 5. Tính toán thống kê tổng quát
    total_reviews = Review.objects.count()
    total_reviewers = Review.objects.values('user').distinct().count()

    return render(request, 'core/staff/review_management.html', {
        'books': page_obj,
        'query': query,
        'total_reviews': total_reviews,
        'total_reviewers': total_reviewers
    })
# ==========================================
# 4. QUẢN LÝ SỰ KIỆN & TIN TỨC (DÀNH CHO THỦ THƯ)
# ==========================================
# Kiểm tra quyền thủ thư
def is_staff_member(user):
    return user.is_authenticated and (user.role in ['STAFF', 'ADMIN'] or user.is_superuser)

@user_passes_test(is_staff_member)
def staff_event_list(request):
    """Trang danh sách sự kiện dành riêng cho Thủ thư"""
    query = request.GET.get('search_query', '').strip()
    now = timezone.now()
    
    # Ưu tiên sự kiện chưa kết thúc lên đầu, đã kết thúc xuống cuối
    events = Event.objects.all().prefetch_related('eventregistration_set__user').annotate(
        is_ended=Case(
            When(end_date__lt=now, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('is_ended', '-start_date')
    
    # Tìm kiếm theo tên hoặc địa điểm
    if query:
        events = events.filter(
            Q(title__icontains=query) |
            Q(location__icontains=query)
        ).distinct()
        
    # Phân trang 10 sự kiện/trang
    page_number = request.GET.get('page', 1)
    paginator = Paginator(events, 10)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/staff/event_management.html', {
        'events': page_obj,
        'query': query,
        'now': now
    })

@user_passes_test(is_staff_member)
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Thêm sự kiện mới thành công!")
            return redirect('staff_event_list') # Đã sửa hướng redirect
    else:
        form = EventForm()
    return render(request, 'core/staff/event_form.html', {'form': form, 'title': 'Thêm sự kiện'})

@user_passes_test(is_staff_member)
def event_edit(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cập nhật sự kiện '{event.title}' thành công!")
            return redirect('staff_event_list') # Đã sửa hướng redirect
    else:
        form = EventForm(instance=event)
    return render(request, 'core/staff/event_form.html', {'form': form, 'title': 'Chỉnh sửa sự kiện'})

@user_passes_test(is_staff_member)
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    title = event.title
    event.delete()
    messages.success(request, f"Đã xóa sự kiện '{title}'.")
    return redirect('staff_event_list') # Đã sửa hướng redirect