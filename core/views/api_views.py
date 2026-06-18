# file: core/views/api_views.py
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

# Import models từ app core
from core.models import Book,Event, EventRegistration, Wishlist, Review, BorrowTransaction, Notification

# ==========================================
# 1. API CƠ BẢN DÀNH CHO BÊN THỨ 3 (GET, POST, DELETE)
# ==========================================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,) # Cho phép ai cũng gọi được API này
    serializer_class = RegisterSerializer
def api_get_books(request):
    if request.method == 'GET':
        books = list(Book.objects.values('id', 'title', 'author', 'quantity'))
        return JsonResponse({'status': 200, 'message': 'Thành công', 'data': books})

@csrf_exempt 
def api_create_book(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            if not data.get('title') or len(data.get('title')) < 2:
                return JsonResponse({'status': 400, 'message': 'Lỗi: Tên sách không được để trống hoặc quá ngắn!'}, status=400)
            if not data.get('author'):
                return JsonResponse({'status': 400, 'message': 'Lỗi: Thiếu tên tác giả!'}, status=400)
            if data.get('quantity', 0) < 0:
                return JsonResponse({'status': 400, 'message': 'Lỗi: Số lượng sách không được nhỏ hơn 0!'}, status=400)

            book = Book.objects.create(
                title=data['title'],
                author=data['author'],
                quantity=data.get('quantity', 0),
                category_id=data.get('category_id', 1) 
            )
            return JsonResponse({'status': 201, 'message': 'Tạo sách thành công!', 'book_id': book.id}, status=201)
            
        except Exception as e:
            return JsonResponse({'status': 400, 'message': f'Lỗi hệ thống: {str(e)}'}, status=400)

@csrf_exempt
def api_delete_book(request, book_id):
    if request.method == 'DELETE':
        try:
            book = Book.objects.get(id=book_id)
            book.delete()
            return JsonResponse({'status': 204, 'message': f'Đã xóa sách có ID {book_id} thành công!'})
        except Book.DoesNotExist:
            return JsonResponse({'status': 404, 'message': 'Lỗi: Không tìm thấy sách để xóa!'}, status=404)

# ==========================================
# 2. API PHỤC VỤ DASHBOARD VÀ TÌM KIẾM AJAX
# ==========================================

@login_required 
def admin_chart_data(request):
    # Cho phép nếu là superuser HOẶC có role STAFF/ADMIN
    is_authorized = request.user.is_superuser or \
                    request.user.is_staff or \
                    getattr(request.user, 'role', '') in ['STAFF', 'ADMIN']

    if is_authorized:
        # 1. Thống kê trạng thái mượn sách
        borrowed = BorrowTransaction.objects.filter(status='BORROWED').count()
        pending = BorrowTransaction.objects.filter(status='PENDING').count()
        returned = BorrowTransaction.objects.filter(status='RETURNED').count()
        overdue = BorrowTransaction.objects.filter(status='OVERDUE').count()

        # 2. Thống kê sách mượn nhiều nhất
        from django.db.models import Count
        top_books = Book.objects.annotate(
            borrow_count=Count('borrow_records')
        ).filter(borrow_count__gt=0).order_by('-borrow_count')[:5]
        
        top_labels = [book.title[:20] + '...' if len(book.title) > 20 else book.title for book in top_books]
        top_data = [book.borrow_count for book in top_books]

        return JsonResponse({
            'status_labels': ['Đang mượn', 'Chờ duyệt', 'Đã trả', 'Quá hạn'],
            'status_data': [borrowed, pending, returned, overdue],
            'top_labels': top_labels,
            'top_data': top_data
        })
    
    return JsonResponse({'error': 'Bạn không có quyền xem dữ liệu này!'}, status=403)

def live_search_api(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        books = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )[:5]
        
        results = []
        for book in books:
            # ĐÃ SỬA: Dùng get_cover() để tự động xử lý link /media/ hoặc http
            if hasattr(book, 'get_cover'):
                image_url = book.get_cover() if callable(book.get_cover) else book.get_cover
            else:
                image_url = book.cover_image.url if hasattr(book.cover_image, 'url') and book.cover_image else '/static/img/default-book.png'
            
            results.append({
                'id': book.id,
                'title': book.title,
                'author': book.author if book.author else 'Chưa rõ',
                'cover_image': image_url,
                'price': book.price,
                'url': reverse('book_detail', args=[book.id]) 
            })
            
        return JsonResponse({'status': 'success', 'data': results})
        
    return JsonResponse({'status': 'empty', 'data': []})

# ==========================================
# 3. API TƯƠNG TÁC NGƯỜI DÙNG (YÊU THÍCH, ĐÁNH GIÁ)
# ==========================================

@require_POST 
def toggle_wishlist_api(request, book_id):
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': 'Vui lòng đăng nhập để lưu sách yêu thích!', 
            'redirect': reverse('login')
        })
    book = get_object_or_404(Book, id=book_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, book=book).first()
    
    if wishlist_item:
        wishlist_item.delete()
        is_wished = False
    else:
        Wishlist.objects.create(user=request.user, book=book)
        is_wished = True
        
    return JsonResponse({
        'status': 'success',
        'is_wished': is_wished
    })

@require_POST
def api_add_review(request, book_id):
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': 'Vui lòng đăng nhập để đánh giá sách!', 
            'redirect': reverse('login')
        })
    book = get_object_or_404(Book, id=book_id)
    rating = request.POST.get('rating')
    comment = request.POST.get('comment')

    if not rating or not comment:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập đủ thông tin.'})

    if Review.objects.filter(user=request.user, book=book).exists():
         return JsonResponse({'status': 'error', 'message': 'Bạn đã đánh giá sách này rồi.'})

    review = Review.objects.create(
        user=request.user,
        book=book,
        rating=int(rating),
        comment=comment
    )

    avatar_url = request.user.avatar_url if hasattr(request.user, 'avatar_url') and request.user.avatar_url else '/static/img/user.jpg'
    full_name = request.user.get_full_name() or request.user.username
    stars_html = '⭐' * review.rating

    return JsonResponse({
        'status': 'success',
        'review': {
            'author': full_name,
            'avatar': avatar_url,
            'stars': stars_html,
            'date': format(review.created_at, 'd/m/Y'),
            'comment': review.comment
        }
    })

# ==========================================
# 4. API TẢI THÊM DỮ LIỆU (LOAD MORE / INFINITE SCROLL)
# ==========================================
def api_load_more_books(request):
    page = int(request.GET.get('page', 1))
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    sort = request.GET.get('sort', 'newest')
    is_premium = request.GET.get('is_premium', 'false')

    books_list = Book.objects.all()

    if is_premium == 'true':
        books_list = books_list.filter(price__gt=0)

    if category_id:
        books_list = books_list.filter(category_id=category_id)
    if query:
        books_list = books_list.filter(
            Q(title__icontains=query) | Q(author__icontains=query) | Q(category__name__icontains=query)
        ).distinct()

    if sort == 'title':
        books_list = books_list.order_by('title')
    elif sort == 'oldest':
        books_list = books_list.order_by('created_at')
    else:
        books_list = books_list.order_by('-created_at')

    wishlist_ids = []
    borrowed_ids = []
    pending_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True))
        borrowed_ids = list(BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True))
        pending_ids = list(BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True))
        overdue_ids = list(BorrowTransaction.objects.filter(user=request.user, status='OVERDUE').values_list('book_id', flat=True))

    paginator = Paginator(books_list, 6) 
    
    try:
        books = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})

    data = []
    for b in books:
        if b.id in pending_ids: btn_status = 'PENDING'
        elif b.id in overdue_ids: btn_status = 'OVERDUE'
        elif b.id in borrowed_ids: btn_status = 'BORROWED'
        elif b.quantity <= 0: btn_status = 'OUT_OF_STOCK'
        elif b.price and b.price > 0: btn_status = 'VIP'
        else: btn_status = 'AVAILABLE'

        # ĐÃ SỬA: Lấy đường dẫn ảnh an toàn 100% (tự động nhận diện property hay method)
        if hasattr(b, 'get_cover'):
            image_url = b.get_cover() if callable(b.get_cover) else b.get_cover
        elif b.cover_image and hasattr(b.cover_image, 'url'):
            image_url = b.cover_image.url
        else:
            # Nếu sách không có ảnh, tự động trả về đường dẫn ảnh mặc định
            image_url = '/static/img/default-book.png' 

        data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author if b.author else 'Chưa rõ',
            'category_name': b.category.name if getattr(b, 'category', None) else 'Khác', 
            'cover_image': image_url,
            'price': b.price,
            'quantity': b.quantity,
            'btn_status': btn_status,
            'is_wished': b.id in wishlist_ids,
            'url': reverse('book_detail', args=[b.id]),
            'borrow_url': reverse('borrow_book', args=[b.id]),
            'wishlist_api_url': reverse('api_toggle_wishlist', args=[b.id])
        })

    return JsonResponse({
        'status': 'success',
        'data': data,
        'has_next': books.has_next()
    })

@login_required
def api_unread_notification_count(request):
    count = Notification.objects.filter(user=request.user, status='UNREAD').count()
    return JsonResponse({'status': 'success', 'unread_count': count})

@login_required
def api_load_more_notifications(request):
    page = int(request.GET.get('page', 1))
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifications_list, 8) 
    
    try:
        notifications = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})
        
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'message': n.message,
            'type': n.type,
            'status': n.status,
            'time_since': timesince(n.created_at) + " trước"
        })
        
    Notification.objects.filter(id__in=[n.id for n in notifications], status='UNREAD').update(status='READ')
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': notifications.has_next()})

@login_required
def api_load_more_history(request):
    page = int(request.GET.get('page', 1))
    
    # ---> ĐÃ SỬA: Thêm logic sắp xếp y như trong borrow_views.py <---
    history_list = BorrowTransaction.objects.filter(user=request.user).annotate(
        status_priority=Case(
            When(status='OVERDUE', then=Value(1)),   # Quá hạn lên top 1
            When(status='BORROWED', then=Value(2)),  # Đang mượn top 2
            When(status='PENDING', then=Value(3)),   # Chờ duyệt top 3
            When(status='CANCELLED', then=Value(4)), # Đã hủy top 4
            When(status='RETURNED', then=Value(5)),  # Đã trả xuống cuối
            default=Value(6),
            output_field=IntegerField(),
        )
    ).order_by('status_priority', '-created_at')
    
    paginator = Paginator(history_list, 8)
    
    try:
        history = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})
        
    data = []
    for item in history:
        # Xử lý ảnh an toàn
        if hasattr(item.book, 'get_cover'):
            cover_image = item.book.get_cover() if callable(item.book.get_cover) else item.book.get_cover
        else:
            cover_image = item.book.cover_image.url if hasattr(item.book.cover_image, 'url') and item.book.cover_image else '/static/img/default-book.png'
        
        data.append({
            'id': item.id,
            'book_title': item.book.title,
            'book_author': item.book.author or "Chưa rõ",
            'cover_image': cover_image,
            'borrow_date': item.borrow_date.strftime("%d/%m/%Y") if item.borrow_date else '-',
            'due_date': item.due_date.strftime("%d/%m/%Y") if item.due_date else '-',
            'return_date': item.return_date.strftime("%d/%m/%Y") if item.return_date else '-',
            'status': item.status,
            'is_late': getattr(item, 'is_late', False), 
            'penalty_amount': getattr(item, 'penalty_amount', 0),
            'return_url': reverse('return_book', args=[item.id]),
            
            # ---> ĐÃ THÊM: Truyền dữ liệu Ca Trực và Ngày Hẹn cho JS xử lý <---
            'pickup_shift': getattr(item, 'pickup_shift', ''),
            'pickup_date': item.pickup_date.strftime("%d/%m/%Y") if getattr(item, 'pickup_date', None) else '-'
        })
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': history.has_next()})

@login_required
def api_load_more_wishlist(request):
    page = int(request.GET.get('page', 1))
    wishlist_items = Wishlist.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(wishlist_items, 6)
    
    try:
        items = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})
        
    borrowed_ids = list(BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True))
    pending_ids = list(BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True))
    overdue_ids = list(BorrowTransaction.objects.filter(user=request.user, status='OVERDUE').values_list('book_id', flat=True))

    data = []
    for item in items:
        b = item.book
        
        if b.id in pending_ids: btn_status = 'PENDING'
        elif b.id in overdue_ids: btn_status = 'OVERDUE'
        elif b.id in borrowed_ids: btn_status = 'BORROWED'
        elif b.quantity <= 0: btn_status = 'OUT_OF_STOCK'
        elif b.price and b.price > 0: btn_status = 'VIP'
        else: btn_status = 'AVAILABLE'

        if hasattr(b, 'get_cover'):
            image_url = b.get_cover() if callable(b.get_cover) else b.get_cover
        else:
            image_url = b.cover_image.url if hasattr(b.cover_image, 'url') and b.cover_image else '/static/img/default-book.png'

        data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author or "Chưa rõ",
            'cover_image': image_url,
            'price': b.price,
            'quantity': b.quantity,
            'btn_status': btn_status,
            'is_wished': True, 
            'url': reverse('book_detail', args=[b.id]),
            'borrow_url': reverse('borrow_book', args=[b.id]),
            'wishlist_api_url': reverse('api_toggle_wishlist', args=[b.id])
        })
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': items.has_next()})
@require_POST
def api_toggle_event_registration(request, event_id):
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': 'Vui lòng đăng nhập để đăng ký tham gia sự kiện!', 
            'redirect': reverse('login')
        })
    event = get_object_or_404(Event, id=event_id)
    
    # Kiểm tra sự kiện đã kết thúc chưa
    if event.end_date and event.end_date < timezone.now():
        return JsonResponse({'status': 'error', 'message': 'Sự kiện này đã kết thúc!'})
        
    registration = EventRegistration.objects.filter(user=request.user, event=event).first()
    
    if registration:
        # Nếu đã tham gia -> Bấm lần nữa là Hủy
        registration.delete()
        return JsonResponse({'status': 'success', 'is_registered': False, 'message': 'Đã hủy đăng ký sự kiện.', 'count': event.registered_count()})
    else:
        # Kiểm tra xem đã đầy chỗ chưa
        if event.max_participants > 0 and event.registered_count() >= event.max_participants:
            return JsonResponse({'status': 'error', 'message': 'Sự kiện này đã đủ số lượng người tham gia!'})
            
        # Đăng ký mới
        EventRegistration.objects.create(user=request.user, event=event)
        return JsonResponse({'status': 'success', 'is_registered': True, 'message': 'Đăng ký tham gia thành công!', 'count': event.registered_count()})

