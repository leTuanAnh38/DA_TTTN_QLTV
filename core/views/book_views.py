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

def guide_view(request):
    """Trang hướng dẫn sử dụng thư viện cho sinh viên"""
    return render(request, 'core/pages/guide.html')

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        full_message = f"HỆ THỐNG THƯ VIỆN ALOVU - CÓ LIÊN HỆ MỚI\n\n" \
                       f"Từ: {name}\n" \
                       f"Email: {email}\n\n" \
                       f"Nội dung lời nhắn:\n{message}"

        try:
            send_mail(
                subject=f"[Alovu Contact] {subject}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['tuananhih271@gmail.com'], 
                fail_silently=False,
            )
            messages.success(request, f'Cảm ơn {name}! Lời nhắn của bạn đã được gửi thành công đến ban quản trị.')
        except Exception as e:
            messages.error(request, 'Có lỗi xảy ra khi gửi email. Vui lòng thử lại sau.')

        return redirect('contact')
        
    return render(request, 'core/pages/contact.html')


# ==========================================
# 2. DANH SÁCH SÁCH & LỌC/TÌM KIẾM
# ==========================================

def book_list(request):
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'newest')  
    category_id = request.GET.get('category', '') 
    
    books_list = Book.objects.all() 
    categories = Category.objects.all()

    if category_id:
        books_list = books_list.filter(category_id=category_id)

    if query:
        books_list = books_list.filter(
            Q(title__icontains=query) |          
            Q(author__icontains=query) |         
            Q(category__name__icontains=query)   
        ).distinct()

    if sort == 'title':
        books_list = books_list.order_by('title') 
    elif sort == 'oldest':
        books_list = books_list.order_by('created_at') 
    else:
        books_list = books_list.order_by('-created_at') 

    wishlist_book_ids = []
    borrowed_book_ids = []
    pending_book_ids = [] 
    overdue_book_ids = []

    if request.user.is_authenticated:
        wishlist_book_ids = Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True)
        borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
        pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)
        overdue_book_ids = BorrowTransaction.objects.filter(user=request.user, status='OVERDUE').values_list('book_id', flat=True)

    paginator = Paginator(books_list, 6) 
    page = request.GET.get('page')
    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)

    context = {
        'books': books, 
        'categories': categories,
        'query': query,
        'current_sort': sort,        
        'current_category': category_id, 
        'category_obj': Category.objects.filter(id=category_id).first() if category_id else None,
        'wishlist_book_ids': list(wishlist_book_ids),
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids),
        'overdue_book_ids': list(overdue_book_ids)
    }
    return render(request, 'core/books/book_list.html', context)


def premium_book_list(request):
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'newest')  
    category_id = request.GET.get('category', '') 
    
    books_list = Book.objects.filter(price__gt=0)
    categories = Category.objects.all()

    if category_id:
        books_list = books_list.filter(category_id=category_id)

    if query:
        books_list = books_list.filter(
            Q(title__icontains=query) |          
            Q(author__icontains=query) |         
            Q(category__name__icontains=query)   
        ).distinct()

    if sort == 'title':
        books_list = books_list.order_by('title') 
    elif sort == 'oldest':
        books_list = books_list.order_by('created_at') 
    else:
        books_list = books_list.order_by('-created_at') 

    paginator = Paginator(books_list, 6) 
    page = request.GET.get('page')
    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)

    borrowed_book_ids = []
    pending_book_ids = []
    overdue_book_ids = []
    wishlist_book_ids = []
    
    if request.user.is_authenticated:
        borrowed_book_ids = BorrowTransaction.objects.filter(
            user=request.user, status='BORROWED'
        ).values_list('book_id', flat=True)
        
        pending_book_ids = BorrowTransaction.objects.filter(
            user=request.user, status='PENDING'
        ).values_list('book_id', flat=True)

        overdue_book_ids = BorrowTransaction.objects.filter(
            user=request.user, status='OVERDUE'
        ).values_list('book_id', flat=True)
        
        wishlist_book_ids = Wishlist.objects.filter(
            user=request.user
        ).values_list('book_id', flat=True)
        
    return render(request, 'core/books/premium_books.html', {
        'books': books, 
        'categories': categories,
        'query': query,
        'current_sort': sort,        
        'current_category': category_id,
        'category_obj': Category.objects.filter(id=category_id).first() if category_id else None,
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids),
        'overdue_book_ids': list(overdue_book_ids),
        'wishlist_book_ids': list(wishlist_book_ids)
    })


# ==========================================
# 3. CHI TIẾT SÁCH & ĐÁNH GIÁ
# ==========================================

def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    reviews = book.reviews.all().order_by('-created_at')
    
    user_has_reviewed = False
    if request.user.is_authenticated:
        user_has_reviewed = Review.objects.filter(book=book, user=request.user).exists()
    
    recommended_books = Book.objects.filter(
        category=book.category
    ).exclude(id=book.id).order_by('?')[:4]

    if recommended_books.count() < 4:
        additional_count = 4 - recommended_books.count()
        additional_books = Book.objects.exclude(
            id__in=[book.id] + [b.id for b in recommended_books]
        ).order_by('-created_at')[:additional_count]
        recommended_books = list(recommended_books) + list(additional_books)

    borrowed_book_ids = []
    pending_book_ids = [] 
    overdue_book_ids = []
    wishlist_book_ids = []
    
    if request.user.is_authenticated:
        borrowed_book_ids = BorrowTransaction.objects.filter(
            user=request.user, 
            status='BORROWED'
        ).values_list('book_id', flat=True)
        
        pending_book_ids = BorrowTransaction.objects.filter(
            user=request.user, 
            status='PENDING'
        ).values_list('book_id', flat=True)

        overdue_book_ids = BorrowTransaction.objects.filter(
            user=request.user, 
            status='OVERDUE'
        ).values_list('book_id', flat=True)

        wishlist_book_ids = Wishlist.objects.filter(
            user=request.user
        ).values_list('book_id', flat=True)
    
    return render(request, 'core/books/book_detail.html', {
        'book': book,
        'reviews': reviews,
        'recommended_books': recommended_books, 
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids), 
        'overdue_book_ids': list(overdue_book_ids),
        'wishlist_book_ids': list(wishlist_book_ids),
        'user_has_reviewed': user_has_reviewed  
    })

@login_required(login_url='login')
def add_review(request, book_id):
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        if Review.objects.filter(book=book, user=request.user).exists():
            messages.error(request, "Bạn đã đánh giá cuốn sách này rồi! Mỗi người chỉ được đánh giá 1 lần.")
            return redirect('book_detail', book_id=book_id)
            
        raw_rating = request.POST.get('rating', '')
        comment = request.POST.get('comment', '').strip()
        errors = []
        
        try:
            rating = int(raw_rating)
            if rating < 1 or rating > 5:
                errors.append("Điểm đánh giá phải từ 1 đến 5 sao.")
        except ValueError:
            errors.append("Điểm đánh giá không hợp lệ.")
            
        if not comment:
            errors.append("Bạn chưa nhập nội dung nhận xét.")
        elif len(comment) > 500:
            errors.append("Nội dung nhận xét quá dài (tối đa 500 ký tự).")
            
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('book_detail', book_id=book_id)
            
        Review.objects.create(
            book=book,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Cảm ơn Bạn đã để lại nhận xét!")
    
    return redirect('book_detail', book_id=book_id)
def event_list(request):
    # Lấy các sự kiện đang mở và sắp xếp theo ngày gần nhất
    events = Event.objects.filter(is_active=True).order_by('start_date')
    
    # Lấy danh sách ID các sự kiện user đã đăng ký để đổi màu nút
    registered_event_ids = []
    if request.user.is_authenticated:
        registered_event_ids = EventRegistration.objects.filter(user=request.user).values_list('event_id', flat=True)

    return render(request, 'core/events/event_list.html', {
        'events': events,
        'registered_event_ids': registered_event_ids,
        'now': timezone.now()
    })