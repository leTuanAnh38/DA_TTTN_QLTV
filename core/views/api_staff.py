from django.contrib.auth.decorators import user_passes_test
from django.db.models import Case, When, Value, IntegerField
import json
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.timesince import timesince
from django.utils.dateformat import format
from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.decorators import user_passes_test
from core.serializers import RegisterSerializer
from django.utils import timezone
from core.models import Book, Wishlist, Review, BorrowTransaction, Notification
# Hàm kiểm tra xem người dùng có phải là Thủ thư (Staff) không
def is_staff(user):
    return user.is_authenticated and user.role in ['STAFF', 'ADMIN']

@user_passes_test(is_staff, login_url='login')
def api_staff_load_more_books(request):
    page = request.GET.get('page', 1)
    query = request.GET.get('q', '')
    
    books = Book.objects.all().order_by('-created_at')
    if query:
        books = books.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) |
            Q(location__icontains=query)
        )
        
    paginator = Paginator(books, 10)
    try:
        books_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})
        
    data = []
    for b in books_page:
        # Tính % thanh tiến độ kho sách
        percent = int((b.quantity / b.initial_quantity) * 100) if getattr(b, 'initial_quantity', 0) > 0 else 0
        
        # Xử lý ảnh an toàn
        if hasattr(b, 'get_cover'):
            image_url = b.get_cover() if callable(b.get_cover) else b.get_cover
        else:
            image_url = '/static/img/default-book.png'
            
        data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author or 'Chưa rõ',
            'cover_image': image_url,
            'category_name': b.category.name if b.category else 'Khác',
            'quantity': b.quantity,
            'initial_quantity': b.initial_quantity,
            'percent': percent,
            'status': b.status,
            'status_display': dict(Book.STATUS_CHOICES).get(b.status, b.status),
            'edit_url': reverse('edit_book', args=[b.id]),
            'delete_url': reverse('delete_book', args=[b.id]),
        })
        
    return JsonResponse({
        'status': 'success',
        'data': data,
        'has_next': books_page.has_next()
    })

@user_passes_test(is_staff, login_url='login')
def api_staff_load_more_borrows(request):
    page = request.GET.get('page', 1)
    query = request.GET.get('q', '').strip()

    # Dùng y chang logic sắp xếp của Views
    transactions = BorrowTransaction.objects.select_related('user', 'book').annotate(
        status_priority=Case(
            When(status='PENDING', then=Value(1)),
            When(status='OVERDUE', then=Value(2)),
            When(status='BORROWED', then=Value(3)),
            When(status='RETURNED', then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
    )

    if query:
        transactions = transactions.filter(
            Q(user__msv__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query)
        ).distinct()

    # Sắp xếp lại giống hệt
    transactions = transactions.order_by('status_priority', '-created_at')

    # Phân trang
    paginator = Paginator(transactions, 10)
    try:
        trans_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})

    data = []
    today = timezone.now().date()
    
    for t in trans_page:
        # Kiểm tra quá hạn
        is_overdue = t.status == 'BORROWED' and t.due_date and t.due_date < today

        data.append({
            'id': t.id,
            'user_name': t.user.get_full_name() or t.user.username,
            'user_msv': getattr(t.user, 'msv', ''),
            'book_title': t.book.title,
            'due_date': t.due_date.strftime("%d/%m/%Y") if t.due_date else '',
            'status': t.status,
            'is_overdue': is_overdue,
            'reason': getattr(t, 'reason', ''),
            'book_price': t.book.price if t.book.price else 0,
            'is_paid': getattr(t, 'is_paid', False),
            'payment_method': getattr(t, 'payment_method', 'FREE'),
            # Tạo sẵn link thao tác
            'confirm_return_url': reverse('staff_confirm_return', args=[t.id]),
            'approve_borrow_url': reverse('staff_approve_borrow', args=[t.id]),
        })

    return JsonResponse({
        'status': 'success',
        'data': data,
        'has_next': trans_page.has_next()
    })

@user_passes_test(is_staff, login_url='login')
def api_staff_get_book_reviews(request, book_id):
    """Lấy danh sách đánh giá của một cuốn sách cụ thể để hiển thị trong Modal"""
    book = get_object_or_404(Book, id=book_id)
    reviews = Review.objects.filter(book=book).order_by('-created_at')
    
    data = []
    for r in reviews:
        data.append({
            'user_name': r.user.get_full_name() or r.user.username,
            'user_avatar': r.user.avatar_url,
            'rating': r.rating,
            'comment': r.comment or 'Không có nội dung nhận xét.',
            'created_at': r.created_at.strftime("%d/%m/%Y %H:%M")
        })
        
    return JsonResponse({
        'status': 'success',
        'book_title': book.title,
        'total_reviewers': reviews.count(),
        'reviews': data
    })