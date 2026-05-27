# file: core/views/book_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Avg
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from core.models import Event, EventRegistration
# Import models và services từ app core
from core.models import Book, Category, BorrowTransaction, Wishlist, Review
from core.services import check_and_create_due_reminders

# ==========================================
# 1. TRANG CHỦ & CÁC TRANG THÔNG TIN (TĨNH)
# ==========================================

def home(request):
    if request.user.is_authenticated:
        check_and_create_due_reminders(request.user)

    featured_books = Book.objects.all().order_by('-created_at')[:5]
    recommended_books = Book.objects.all().order_by('?')[:3] 
    books = Book.objects.all().order_by('-created_at')[:6]
    categories = Category.objects.all()

    popular_books = Book.objects.annotate(
        borrow_count=Count('borrow_records')
    ).filter(borrow_count__gt=0).order_by('-borrow_count')[:3]

    top_rated_books = Book.objects.annotate(
        avg_rating=Avg('reviews__rating') 
    ).filter(avg_rating__gte=4).order_by('-avg_rating')[:3]

    wishlist_book_ids = []
    borrowed_book_ids = []
    pending_book_ids = [] 
    overdue_book_ids = []
    
    if request.user.is_authenticated:
        wishlist_book_ids = Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True)
        borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
        pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)
        overdue_book_ids = BorrowTransaction.objects.filter(user=request.user, status='OVERDUE').values_list('book_id', flat=True)

    return render(request, 'core/pages/index.html', {
        'featured_books': featured_books,
        'recommended_books': recommended_books, 
        'books': books,
        'categories': categories,
        'popular_books': popular_books,      
        'top_rated_books': top_rated_books,  
        'wishlist_book_ids': list(wishlist_book_ids),
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids),
        'overdue_book_ids': list(overdue_book_ids)
    })
