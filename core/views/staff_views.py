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
