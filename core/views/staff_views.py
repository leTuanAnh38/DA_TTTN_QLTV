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

