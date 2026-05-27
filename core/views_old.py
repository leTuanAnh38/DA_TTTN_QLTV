import re
import json
from datetime import timedelta
from django.utils.timesince import timesince
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.forms import PasswordChangeForm, AuthenticationForm
from django.contrib.auth import update_session_auth_hash, authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.utils.dateformat import format
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction as db_transaction
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from .models import Book, BorrowTransaction, Review, Category, Wishlist, Penalty, User, Notification
from .forms import CustomUserCreationForm, BookForm
from .services import check_and_create_due_reminders

def user_logout(request):
    logout(request)
    messages.success(request, 'Bạn đã đăng xuất thành công!')
    return redirect('home')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đăng ký tài khoản thành công! Vui lòng đăng nhập.')
            return redirect('home') 
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'core/register.html', {'form': form})

def user_login(request):
    # 1. Kiểm tra nếu đã đăng nhập từ trước
    if request.user.is_authenticated:
        user = request.user
        if user.is_superuser or user.role == 'ADMIN':
            return redirect('/admin/')
        elif user.is_staff or user.role == 'STAFF':
            return redirect('staff_borrow_management')
        return redirect('home')

    # 2. Xử lý khi nhấn nút Đăng nhập (POST)
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user) 
                messages.success(request, f'Chào mừng {username} đã quay lại!')
                
                # PHÂN LUỒNG SAU ĐĂNG NHẬP
                if user.is_superuser or user.role == 'ADMIN':
                    return redirect('/admin/') # Admin vào trang quản trị hệ thống
                elif user.is_staff or user.role == 'STAFF':
                    return redirect('staff_borrow_management') # Staff vào trang nghiệp vụ mượn trả
                else:
                    return redirect('home') # Người đọc vào trang chủ
            else:
                messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
        else:
            messages.error(request, 'Thông tin đăng nhập không hợp lệ. Vui lòng kiểm tra lại.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'core/login.html', {'form': form})

@login_required(login_url='login') 
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) 
            messages.success(request, 'Mật khẩu của bạn đã được cập nhật thành công!')
            return redirect('home')
        else:
            messages.error(request, 'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại thông tin bên dưới.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'core/change_password.html', {'form': form})

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

    # [MỚI] 2. LẤY SÁCH ĐƯỢC ĐÁNH GIÁ TỪ 4 SAO TRỞ LÊN (Top 3)
    top_rated_books = Book.objects.annotate(
        avg_rating=Avg('reviews__rating') 
    ).filter(avg_rating__gte=4).order_by('-avg_rating')[:3]

    wishlist_book_ids = []
    borrowed_book_ids = []
    pending_book_ids = [] # Khởi tạo danh sách sách đang chờ duyệt
    
    if request.user.is_authenticated:
        # Lấy danh sách ID sách đã yêu thích
        wishlist_book_ids = Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True)
        
        # Lấy danh sách ID sách đang mượn chưa trả
        borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
        
        # Lấy danh sách ID sách mà sinh viên đã bấm trả, đang chờ Thủ thư xác nhận
        pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)

    return render(request, 'core/index.html', {
        'featured_books': featured_books,
        'recommended_books': recommended_books, 
        'books': books,
        'categories': categories,
        'popular_books': popular_books,      # [MỚI] Truyền sách mượn nhiều ra HTML
        'top_rated_books': top_rated_books,  # [MỚI] Truyền sách đánh giá cao ra HTML
        'wishlist_book_ids': list(wishlist_book_ids),
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids) 
    })
# HÀM BOOK_LIST CHUẨN (Đã gộp cả tìm kiếm, lọc và phân trang)
def book_list(request):
    # Lấy các tham số từ thanh địa chỉ (URL)
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'newest')  # Mặc định là mới nhất
    category_id = request.GET.get('category', '') # Lấy ID danh mục muốn lọc
    
    books_list = Book.objects.all() 
    categories = Category.objects.all()

    # 1. Lọc theo danh mục (nếu người dùng chọn)
    if category_id:
        books_list = books_list.filter(category_id=category_id)

    # 2. Xử lý tìm kiếm (giữ nguyên logic của Khanh)
    if query:
        books_list = books_list.filter(
            Q(title__icontains=query) |          
            Q(author__icontains=query) |         
            Q(category__name__icontains=query)   
        ).distinct()

    # 3. Xử lý Sắp xếp
    if sort == 'title':
        books_list = books_list.order_by('title') # Sắp xếp A-Z theo tiêu đề
    elif sort == 'oldest':
        books_list = books_list.order_by('created_at') # Cũ nhất
    else:
        books_list = books_list.order_by('-created_at') # Mới nhất (mặc định)

    # --- Phần xử lý Wishlist và Borrow ---
    wishlist_book_ids = []
    borrowed_book_ids = []
    pending_book_ids = [] # [MỚI] Khởi tạo danh sách ID sách đang chờ duyệt trả

    if request.user.is_authenticated:
        wishlist_book_ids = Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True)
        borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
        # [MỚI] Truy vấn các sách đang ở trạng thái PENDING
        pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)

    # 4. Phân trang (Giữ nguyên của Khanh)
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
        'current_sort': sort,        # Gửi lại để giữ trạng thái dropdown
        'current_category': category_id, # Gửi lại để giữ trạng thái dropdown
        'wishlist_book_ids': list(wishlist_book_ids),
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids) # [MỚI] Gửi biến này ra template
    }
    return render(request, 'core/book_list.html', context)
def guide_view(request):
    """Trang hướng dẫn sử dụng thư viện cho sinh viên"""
    return render(request, 'core/guide.html')

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        # Đóng gói nội dung email để gửi cho bạn
        full_message = f"HỆ THỐNG THƯ VIỆN ALOVU - CÓ LIÊN HỆ MỚI\n\n" \
                       f"Từ: {name}\n" \
                       f"Email: {email}\n\n" \
                       f"Nội dung lời nhắn:\n{message}"

        try:
            # Gửi email thực tế
            send_mail(
                subject=f"[Alovu Contact] {subject}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['tuananhih271@gmail.com'], # <--- Email của Khanh nhận tin
                fail_silently=False,
            )
            messages.success(request, f'Cảm ơn {name}! Lời nhắn của bạn đã được gửi thành công đến ban quản trị.')
        except Exception as e:
            messages.error(request, 'Có lỗi xảy ra khi gửi email. Vui lòng thử lại sau.')

        return redirect('contact')
        
    return render(request, 'core/contact.html')

# [MỚI] 1. HÀM HIỂN THỊ DANH SÁCH SÁCH VIP CÓ PHÍ
def premium_book_list(request):
    # Lấy những sách có thuộc tính price (giá tiền) lớn hơn 0
    books_list = Book.objects.filter(price__gt=0).order_by('-created_at')
    
    paginator = Paginator(books_list, 6) 
    page = request.GET.get('page')
    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)
    # ---------------------------------------------------------

    # Khởi tạo các danh sách ID trống
    borrowed_book_ids = []
    pending_book_ids = []
    wishlist_book_ids = []
    
    if request.user.is_authenticated:
        # Lấy danh sách ID sách đang mượn
        borrowed_book_ids = BorrowTransaction.objects.filter(
            user=request.user, status='BORROWED'
        ).values_list('book_id', flat=True)
        
        # Lấy danh sách ID sách đang chờ duyệt
        pending_book_ids = BorrowTransaction.objects.filter(
            user=request.user, status='PENDING'
        ).values_list('book_id', flat=True)
        
        wishlist_book_ids = Wishlist.objects.filter(
            user=request.user
        ).values_list('book_id', flat=True)
        
    return render(request, 'core/premium_books.html', {
        'books': books, # Truyền biến books đã được phân trang ra giao diện
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids),
        'wishlist_book_ids': list(wishlist_book_ids)
    })
# [ĐÃ NÂNG CẤP] 2. HÀM XỬ LÝ MƯỢN SÁCH (HỖ TRỢ THANH TOÁN)
@login_required(login_url='login')
def borrow_book(request, book_id):
    user = request.user
    
    # 1. KIỂM TRA PHÍ PHẠT
    if user.total_fine > 0:
        messages.error(request, f"Bạn hiện đang có khoản phí phạt chưa thanh toán ({user.total_fine} VNĐ). Vui lòng hoàn tất nghĩa vụ để tiếp tục mượn sách!")
        return redirect('profile')

    # 2. KIỂM TRA HỒ SƠ
    if not user.msv or not user.lop:
        messages.warning(request, "Vui lòng cập nhật MSSV và Lớp trong hồ sơ cá nhân trước khi thực hiện mượn sách!")
        return redirect('profile')

    # 3. Lấy thông tin sách
    book = get_object_or_404(Book, id=book_id)
    
    if book.quantity <= 0:
        messages.error(request, f"Sách '{book.title}' đã hết trong kho!")
        return redirect(request.META.get('HTTP_REFERER', 'book_list'))
    # [MỚI] XỬ LÝ SÁCH CÓ PHÍ VÀ PHƯƠNG THỨC THANH TOÁN
    # Kiểm tra xem sách này có phí không (price > 0)
    is_premium = book.price and book.price > 0

    if request.method == 'POST':
        # Lấy phương thức thanh toán từ Modal HTML gửi lên (Mặc định là FREE nếu k có)
        payment_method = request.POST.get('payment_method', 'FREE')
    else:
        # Nếu mượn sách VIP mà không thông qua nút bấm (gọi GET trực tiếp) -> Chặn lại
        if is_premium:
            messages.warning(request, "Vui lòng chọn phương thức thanh toán tại trang Danh mục để mượn sách VIP!")
            return redirect('premium_books')
        payment_method = 'FREE'

    han_tra = timezone.now().date() + timedelta(days=14)
    
    # Phân loại trạng thái: Sách có phí -> PENDING (Chờ đóng tiền). Sách Free -> BORROWED (Mượn luôn)
    status = 'PENDING' if is_premium else 'BORROWED'
    is_paid = False if is_premium else True

    try:
        with db_transaction.atomic():
            transaction = BorrowTransaction.objects.create(
                user=user,
                book=book,
                due_date=han_tra, 
                status=status,
                payment_method=payment_method, # Lưu cách sinh viên chọn trả tiền
                is_paid=is_paid                # Lưu trạng thái đã nộp tiền chưa
            )

            # Cảnh báo/Thông báo tương ứng
            if is_premium:
                # Dùng dict để dịch chữ CASH thành 'Thanh toán tại quầy' cho đẹp
                payment_display = dict(BorrowTransaction.PAYMENT_CHOICES).get(payment_method, payment_method)
                msg = f"Đã ghi nhận yêu cầu mượn '{book.title}'. Vui lòng thanh toán {book.price:,.0f} VNĐ qua hình thức [{payment_display}] để Thủ thư duyệt!"
            else:
                msg = f"Mượn thành công! Hạn trả cuốn '{book.title}' là ngày {han_tra.strftime('%d/%m/%Y')}."

            # Tạo thông báo hệ thống
            Notification.objects.create(
                user=user,
                message=msg,
                type='SYSTEM',
                status='UNREAD'
            )

            book.quantity -= 1
            book.save()

        messages.success(request, msg)
    except Exception as e:
        messages.error(request, f"Đã có lỗi xảy ra trong quá trình mượn sách: {str(e)}")
    
    # [MỚI] Thông minh hơn: Đang đứng ở trang nào bấm mượn thì tự động F5 lại trang đó
    return redirect(request.META.get('HTTP_REFERER', 'book_list'))

@login_required(login_url='login')
def borrow_history(request):
    history_list = BorrowTransaction.objects.filter(user=request.user).order_by('-created_at')
    
    # Phân trang: Mỗi lần tải 8 giao dịch
    paginator = Paginator(history_list, 8) 
    page = request.GET.get('page', 1)
    
    try:
        history = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        history = paginator.page(1)
        
    return render(request, 'core/borrow_history.html', {'history': history})

# 1. DÀNH CHO NGƯỜI ĐỌC: Chỉ gửi yêu cầu trả sách
@login_required(login_url='login')
def return_book(request, transaction_id):
    # Chỉ lấy những giao dịch đang mượn (BORROWED)
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, user=request.user, status='BORROWED')
    
    try:
        # Chuyển trạng thái sang Chờ xác nhận
        borrow_record.status = 'PENDING'
        borrow_record.save()
        
        # Bỏ hết các logic tính phạt ở đây, chỉ hiển thị thông báo
        messages.success(request, f"Yêu cầu trả cuốn '{borrow_record.book.title}' đã được gửi. Vui lòng mang sách đến quầy để Thủ thư xác nhận.")
    except Exception as e:
        messages.error(request, f"Đã xảy ra lỗi: {str(e)}")
        
    return redirect('borrow_history')

# core/views.py

def book_detail(request, book_id):
    # 1. Lấy thông tin cuốn sách hiện tại
    book = get_object_or_404(Book, id=book_id)
    reviews = book.reviews.all().order_by('-created_at')
    
    # ==========================================
    # [MỚI] KIỂM TRA USER ĐÃ ĐÁNH GIÁ CHƯA
    # ==========================================
    user_has_reviewed = False
    if request.user.is_authenticated:
        user_has_reviewed = Review.objects.filter(book=book, user=request.user).exists()
    
    # 2. LOGIC GỢI Ý THÔNG MINH:
    # - Tìm các cuốn sách cùng Category.
    # - Loại trừ cuốn sách hiện tại (.exclude).
    # - Sắp xếp ngẫu nhiên (.order_by('?')) để mỗi lần F5 sẽ thấy sách mới.
    # - Giới hạn lấy 4 cuốn [:4].
    recommended_books = Book.objects.filter(
        category=book.category
    ).exclude(id=book.id).order_by('?')[:4]

    # Dự phòng: Nếu danh mục này không đủ 4 cuốn, lấy thêm các sách mới nhất khác
    if recommended_books.count() < 4:
        additional_count = 4 - recommended_books.count()
        additional_books = Book.objects.exclude(
            id__in=[book.id] + [b.id for b in recommended_books]
        ).order_by('-created_at')[:additional_count]
        recommended_books = list(recommended_books) + list(additional_books)

    # 3. Kiểm tra sách đang mượn và CHỜ XÁC NHẬN TRẢ [CẬP NHẬT]
    borrowed_book_ids = []
    pending_book_ids = [] # [MỚI] Khởi tạo danh sách chờ duyệt
    
    if request.user.is_authenticated:
        # Lấy danh sách ID sách đang mượn chưa trả
        borrowed_book_ids = BorrowTransaction.objects.filter(
            user=request.user, 
            status='BORROWED'
        ).values_list('book_id', flat=True)
        
        # [MỚI] Lấy danh sách ID sách đang chờ thủ thư xác nhận trả
        pending_book_ids = BorrowTransaction.objects.filter(
            user=request.user, 
            status='PENDING'
        ).values_list('book_id', flat=True)
    
    # 4. Trả về template với thêm biến pending_book_ids
    return render(request, 'core/book_detail.html', {
        'book': book,
        'reviews': reviews,
        'recommended_books': recommended_books, # Dữ liệu gợi ý cho AI/ML section
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids), # [MỚI] Truyền biến này ra template
        'user_has_reviewed': user_has_reviewed  
    })
# core/views.py

@login_required(login_url='login')
def add_review(request, book_id):
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        # [MỚI] KIỂM TRA USER ĐÃ ĐÁNH GIÁ CHƯA
        if Review.objects.filter(book=book, user=request.user).exists():
            messages.error(request, "Bạn đã đánh giá cuốn sách này rồi! Mỗi người chỉ được đánh giá 1 lần.")
            return redirect('book_detail', book_id=book_id)
            
        # 1. Lấy dữ liệu và strip
        raw_rating = request.POST.get('rating', '')
        comment = request.POST.get('comment', '').strip()
        
        errors = []
        
        # 2. VALIDATION RATING
        try:
            rating = int(raw_rating)
            if rating < 1 or rating > 5:
                errors.append("Điểm đánh giá phải từ 1 đến 5 sao.")
        except ValueError:
            errors.append("Điểm đánh giá không hợp lệ.")
            
        # 3. VALIDATION COMMENT (Kiểm tra rỗng và độ dài)
        if not comment:
            errors.append("Bạn chưa nhập nội dung nhận xét.")
        elif len(comment) > 500:
            errors.append("Nội dung nhận xét quá dài (tối đa 500 ký tự).")
            
        # NẾU CÓ LỖI: Trả về thông báo
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('book_detail', book_id=book_id)
            
        # NẾU HỢP LỆ: Lưu vào Database
        Review.objects.create(
            book=book,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Cảm ơn Bạn đã để lại nhận xét!")
    
    return redirect('book_detail', book_id=book_id)

def is_staff(user):
    return user.is_authenticated and user.role in ['STAFF', 'ADMIN']

# HÀM STAFF DASHBOARD CHUẨN (Có hỗ trợ tìm kiếm)
@user_passes_test(is_staff, login_url='login')
def staff_dashboard(request):
    query = request.GET.get('search_staff')
    books = Book.objects.all() 

    if query:
        books = books.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) |
            Q(location__icontains=query) 
        )

    books = books.order_by('-created_at')
    return render(request, 'core/staff/dashboard.html', {'books': books})

# core/views.py

@user_passes_test(is_staff)
def add_book(request):
    if request.method == 'POST':
        # Sử dụng BookForm đã định nghĩa trong forms.py
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Thêm sách '{form.cleaned_data.get('title')}' thành công!")
            return redirect('staff_dashboard')
    else:
        form = BookForm()
    
    # Render ra giao diện staff/book_form.html
    return render(request, 'core/staff/book_form.html', {
        'form': form, 
        'title': 'Thêm sách mới'
    })

@user_passes_test(is_staff)
def edit_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật thông tin sách thành công!")
            return redirect('staff_dashboard')
    else:
        form = BookForm(instance=book)
    return render(request, 'core/staff/book_form.html', {'form': form, 'title': 'Chỉnh sửa sách'})

@user_passes_test(is_staff)
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    book.delete()
    messages.success(request, "Đã xóa sách khỏi hệ thống!")
    return redirect('staff_dashboard')

# Hàm 1: Thêm/Bớt sách yêu thích
@login_required(login_url='login')
def toggle_wishlist(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # Kiểm tra xem cuốn sách này đã có trong danh sách yêu thích của User chưa
    wishlist_item = Wishlist.objects.filter(user=request.user, book=book).first()
    
    if wishlist_item:
        # Nếu có rồi thì xóa đi (Bỏ yêu thích)
        wishlist_item.delete()
        messages.success(request, f"Đã bỏ '{book.title}' khỏi danh sách yêu thích.")
    else:
        # Nếu chưa có thì tạo mới (Thêm yêu thích)
        Wishlist.objects.create(user=request.user, book=book)
        messages.success(request, f"Đã thêm '{book.title}' vào danh sách yêu thích.")
    
    # Lệnh này giúp trình duyệt tự động load lại đúng trang người dùng đang đứng (Trang chủ hoặc Kho sách)
    return redirect(request.META.get('HTTP_REFERER', 'home'))

# Hàm 2: Hiển thị trang Danh sách yêu thích
@login_required(login_url='login')
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).order_by('-created_at')
    
    # Phân trang: Mỗi lần tải 6 cuốn
    paginator = Paginator(wishlist_items, 6) 
    page = request.GET.get('page', 1)
    try:
        items = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        items = paginator.page(1)
        
    borrowed_book_ids = BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True)
    pending_book_ids = BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True)
    
    return render(request, 'core/wishlist.html', {
        'wishlist_items': items, # Truyền biến đã phân trang
        'borrowed_book_ids': list(borrowed_book_ids),
        'pending_book_ids': list(pending_book_ids)
    })

@login_required
def notification_list(request):
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifications_list, 8) # Lần đầu chỉ tải 8 thông báo cho nhẹ
    page = request.GET.get('page', 1)
    
    try:
        notifications = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        notifications = paginator.page(1)
        
    # Đánh dấu đã đọc những thông báo hiện ra
    if notifications:
        Notification.objects.filter(id__in=[n.id for n in notifications], status='UNREAD').update(status='READ')
    
    return render(request, 'core/notifications.html', {'notifications': notifications})

@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        
        # 1. Lấy dữ liệu và dùng .strip() để xóa khoảng trắng thừa ở 2 đầu
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        msv = (request.POST.get('msv') or '').strip()
        lop = (request.POST.get('lop') or '').strip()
        dia_chi = (request.POST.get('dia_chi') or '').strip()
        
        # ==========================================
        # YÊU CẦU 3: VALIDATION DỮ LIỆU ĐẦU VÀO
        # ==========================================
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
            # Kiểm tra xem file tải lên có thực sự là định dạng ảnh không
            if not avatar_file.content_type.startswith('image/'):
                errors.append("File tải lên không phải là định dạng hình ảnh hợp lệ.")
                
        # NẾU CÓ LỖI: Báo lỗi ra màn hình và dừng lại, KHÔNG lưu vào Database
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('profile')
        # ==========================================
        
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
        
    # ==========================================
    # 3. XỬ LÝ KHI TRUY CẬP TRANG (GET REQUEST)
    # ==========================================
    
    # Lấy danh sách đánh giá sách
    user_reviews = Review.objects.filter(user=request.user).select_related('book').order_by('-created_at')
    
    # KIỂM TRA TRẠNG THÁI TIỀN PHẠT ĐỂ HIỂN THỊ NÚT
    has_unpaid = Penalty.objects.filter(user=request.user, status='UNPAID').exists()
    
    processing_penalties = Penalty.objects.filter(user=request.user, status='PROCESSING')
    has_processing = processing_penalties.exists()
    
    # Tính tổng tiền đang chờ duyệt (nếu có)
    processing_amount = processing_penalties.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return render(request, 'core/profile.html', {
        'user_reviews': user_reviews,
        'has_unpaid': has_unpaid,
        'has_processing': has_processing,
        'processing_amount': processing_amount # Gửi số tiền đang chờ duyệt ra ngoài
    })
    
@login_required
def pay_all_penalties(request):
    if request.method == 'POST':
        method = request.POST.get('payment_method', '').strip()
        
        # Lấy danh sách các phương thức hợp lệ từ Model
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

# PHẦN API ENDPOINTS (Dành cho Yêu cầu số 2 & 3)
# 1. READ: Lấy danh sách sách (GET /api/books/)
def api_get_books(request):
    if request.method == 'GET':
        # Lấy dữ liệu từ database và chuyển thành dạng Dictionary
        books = list(Book.objects.values('id', 'title', 'author', 'quantity'))
        return JsonResponse({'status': 200, 'message': 'Thành công', 'data': books})

# 2. CREATE: Thêm sách mới (POST /api/books/add/)
@csrf_exempt # Bỏ qua check CSRF token khi test bằng Postman
def api_create_book(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # YÊU CẦU SỐ 3: Bổ sung Validation cho dữ liệu đầu vào
            if not data.get('title') or len(data.get('title')) < 2:
                return JsonResponse({'status': 400, 'message': 'Lỗi: Tên sách không được để trống hoặc quá ngắn!'}, status=400)
            if not data.get('author'):
                return JsonResponse({'status': 400, 'message': 'Lỗi: Thiếu tên tác giả!'}, status=400)
            if data.get('quantity', 0) < 0:
                return JsonResponse({'status': 400, 'message': 'Lỗi: Số lượng sách không được nhỏ hơn 0!'}, status=400)

            # Thực hiện lưu sách mới vào DB
            # Lưu ý: Cần truyền thêm category_id hợp lệ nếu models yêu cầu
            book = Book.objects.create(
                title=data['title'],
                author=data['author'],
                quantity=data.get('quantity', 0),
                category_id=data.get('category_id', 1) # Giả định category mặc định là 1
            )
            return JsonResponse({'status': 201, 'message': 'Tạo sách thành công!', 'book_id': book.id}, status=201)
            
        except Exception as e:
            return JsonResponse({'status': 400, 'message': f'Lỗi hệ thống: {str(e)}'}, status=400)

# 3. DELETE: Xóa sách (DELETE /api/books/delete/<id>/)
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
# CHỨC NĂNG DÀNH RIÊNG CHO THỦ THƯ (STAFF)
# ==========================================

# 1. Xem toàn bộ lịch sử mượn sách
@user_passes_test(is_staff, login_url='login')
def staff_borrow_management(request):
    # 1. Lấy từ khóa tìm kiếm từ thanh địa chỉ (URL parameter 'q')
    query = request.GET.get('q', '').strip()
    
    # 2. Lấy tất cả giao dịch, dùng select_related để tối ưu tốc độ tải dữ liệu liên kết
    transactions = BorrowTransaction.objects.all().select_related('user', 'book')
    
    # 3. Thực hiện lọc nếu có từ khóa tìm kiếm
    if query:
        transactions = transactions.filter(
            Q(user__msv__icontains=query) |          # Tìm theo MSSV
            Q(user__username__icontains=query) |     # Tìm theo Username
            Q(user__first_name__icontains=query) |   # Tìm theo Tên
            Q(user__last_name__icontains=query)      # Tìm theo Họ
        ).distinct() # Tránh trùng lặp kết quả
        
    # 4. Sắp xếp mới nhất lên đầu
    transactions = transactions.order_by('-created_at')
    
    return render(request, 'core/staff/borrow_management.html', {
        'transactions': transactions,
        'query': query  # Gửi lại từ khóa để hiển thị trong ô nhập liệu
    })
@user_passes_test(is_staff, login_url='login')
def staff_approve_borrow(request, transaction_id):
    # Lấy giao dịch đang ở trạng thái PENDING và chưa thanh toán (is_paid=False)
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, status='PENDING', is_paid=False)
    
    try:
        with db_transaction.atomic():
            # 1. Chuyển trạng thái sang ĐANG MƯỢN
            borrow_record.status = 'BORROWED'
            
            # 2. Cập nhật đã thu tiền
            borrow_record.is_paid = True
            
            # 3. Tính lại hạn trả (14 ngày kể từ lúc thủ thư duyệt)
            borrow_record.borrow_date = timezone.now().date()
            borrow_record.due_date = timezone.now().date() + timedelta(days=14)
            borrow_record.save()
            
            # 4. Gửi thông báo cho sinh viên đến lấy sách
            Notification.objects.create(
                user=borrow_record.user,
                message=f"Thủ thư đã duyệt tiền và giao cuốn VIP '{borrow_record.book.title}' cho bạn. Hạn trả là {borrow_record.due_date.strftime('%d/%m/%Y')}.",
                type='SYSTEM',
                status='UNREAD'
            )
            
        messages.success(request, f"Đã xác nhận thu tiền và giao sách VIP cho sinh viên {borrow_record.user.msv}.")
    except Exception as e:
        messages.error(request, f"Lỗi hệ thống: {str(e)}")
        
    return redirect('staff_borrow_management')
# 2. DÀNH CHO THỦ THƯ: Chốt giao dịch, tính tiền phạt và hoàn sách về kho
@user_passes_test(is_staff, login_url='login')
def staff_confirm_return(request, transaction_id):
    # Cập nhật: Cho phép Thủ thư xác nhận sách khi sinh viên đã gửi yêu cầu (PENDING) 
    # hoặc thủ thư tự ấn trả luôn hộ sinh viên (BORROWED)
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, status__in=['BORROWED', 'PENDING'])
    user = borrow_record.user
    
    try:
        with db_transaction.atomic():
            today = timezone.now().date()
            borrow_record.status = 'RETURNED'
            borrow_record.return_date = today
            borrow_record.save()
            
            # KIỂM TRA TRẢ TRỄ (Logic dồn hết về đây)
            if today > borrow_record.due_date:
                user.points = max(0, user.points - 5)
                days_late = (today - borrow_record.due_date).days
                fine_amount = days_late * 5000
                
                # Tạo phiếu phạt
                Penalty.objects.create(
                    user=user,
                    borrow_transaction=borrow_record,
                    amount=fine_amount,
                    reason=f"Trả sách trễ {days_late} ngày",
                    status='UNPAID'
                )

                # [ĐÃ SỬA] Thông báo khi trả trễ - Thêm cảnh báo TRỪ 5 ĐIỂM
                Notification.objects.create(
                    user=user,
                    message=f"CẢNH BÁO: Thủ thư đã thu hồi cuốn '{borrow_record.book.title}'. Bạn trả trễ {days_late} ngày, hệ thống phạt {fine_amount} VNĐ và TRỪ 5 ĐIỂM tích lũy.",
                    type='SYSTEM',
                    status='UNREAD'
                )
            else:
                user.points += 10 # Cộng điểm nếu trả đúng hạn
                
                # [MỚI] THÔNG BÁO KHI TRẢ ĐÚNG HẠN HOẶC TRƯỚC HẠN
                Notification.objects.create(
                    user=user,
                    message=f"Tuyệt vời! Thủ thư đã xác nhận thu hồi cuốn '{borrow_record.book.title}' thành công. Bạn được cộng 10 điểm thưởng vì trả sách đúng hạn.",
                    type='SYSTEM',
                    status='UNREAD'
                )
            
            user.save() 
            
            # Trả sách lại vào kho
            book = borrow_record.book
            book.quantity += 1
            book.save()
            
            messages.success(request, f"Đã xác nhận thu hồi sách từ Sinh viên {user.msv} (Tên: {user.get_full_name() or user.username}).")
    except Exception as e:
        messages.error(request, f"Lỗi hệ thống: {str(e)}")
        
    return redirect('staff_borrow_management')

# 3. Xem danh sách cần thu tiền phạt
@user_passes_test(is_staff, login_url='login')
def staff_penalty_management(request):
    # Lấy các khoản phạt đang chờ duyệt (PROCESSING) hoặc chưa đóng (UNPAID)
    penalties = Penalty.objects.exclude(status='PAID').order_by('-created_at')
    return render(request, 'core/staff/penalty_management.html', {'penalties': penalties})

# 4. Thủ thư xác nhận đã nhận tiền phạt
@user_passes_test(is_staff, login_url='login')
def staff_confirm_penalty(request, penalty_id):
    # [BẢO MẬT] Chỉ cho phép xác nhận các đơn ở trạng thái UNPAID hoặc PROCESSING
    penalty = get_object_or_404(Penalty, id=penalty_id, status__in=['UNPAID', 'PROCESSING'])
    
    penalty.status = 'PAID'
    penalty.save()
    
    # Gửi thông báo cho sinh viên yên tâm
    Notification.objects.create(
        user=penalty.user,
        message=f"Thủ thư đã xác nhận thu khoản tiền phạt {penalty.amount} VNĐ của bạn. Cảm ơn bạn đã hoàn tất nghĩa vụ!",
        type='SYSTEM',
        status='UNREAD'
    )
    
    messages.success(request, f"Đã xác nhận thu tiền phạt thành công từ sinh viên {penalty.user.msv}.")
    return redirect('staff_penalty_management')

# 1. Trang danh sách chỉ hiện người đọc (Sinh viên)
@user_passes_test(is_staff, login_url='login')
def staff_user_management(request):
    # Lọc bỏ Admin và Staff, chỉ lấy người dùng thường
    readers = User.objects.filter(
        is_staff=False, 
        is_superuser=False
    ).exclude(role__in=['STAFF', 'ADMIN']).order_by('username')
    
    query = request.GET.get('q')
    if query:
        readers = readers.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(msv__icontains=query)
        )
        
    return render(request, 'core/staff/user_management.html', {'readers': readers})

# 2. Trang chi tiết lịch sử và tiền phạt của một người đọc
@user_passes_test(is_staff, login_url='login')
def staff_user_detail(request, user_id):
    reader = get_object_or_404(User, id=user_id)
    
    # Lấy lịch sử mượn sách
    borrow_history = BorrowTransaction.objects.filter(user=reader).order_by('-created_at')
    
    # Lấy danh sách tiền phạt
    penalties = Penalty.objects.filter(user=reader).order_by('-created_at')
    
    return render(request, 'core/staff/user_detail.html', {
        'reader': reader,
        'borrow_history': borrow_history,
        'penalties': penalties
    })

@login_required # Chỉ cần đăng nhập là gọi được, nhưng ta sẽ check quyền bên trong
def admin_chart_data(request):
    # Kiểm tra: Phải là Admin hệ thống HOẶC người có role ADMIN/STAFF
    is_admin = request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN')
    is_staff_user = hasattr(request.user, 'role') and request.user.role == 'STAFF'

    if is_admin or is_staff_user:
        borrowed = BorrowTransaction.objects.filter(status='BORROWED').count()
        pending = BorrowTransaction.objects.filter(status='PENDING').count()
        returned = BorrowTransaction.objects.filter(status='RETURNED').count()
        overdue = BorrowTransaction.objects.filter(status='OVERDUE').count()

        return JsonResponse({
            'labels': ['Đang mượn', 'Chờ xác nhận', 'Đã trả', 'Quá hạn'],
            'data': [borrowed, pending, returned, overdue]
        })
    
    return JsonResponse({'error': 'Bạn không có quyền xem dữ liệu này!'}, status=403)

# Tạo API để thao tác bằng AJAX
@login_required
@require_POST # API đổi trạng thái nên dùng POST cho bảo mật
def toggle_wishlist_api(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # Kiểm tra xem sinh viên đã thả tim cuốn này chưa
    wishlist_item = Wishlist.objects.filter(user=request.user, book=book).first()
    
    if wishlist_item:
        # Nếu có rồi thì xóa đi (Bỏ tim)
        wishlist_item.delete()
        is_wished = False
    else:
        # Nếu chưa có thì tạo mới (Thả tim)
        Wishlist.objects.create(user=request.user, book=book)
        is_wished = True
        
    # Trả về kết quả cho Javascript xử lý dạng JSON
    return JsonResponse({
        'status': 'success',
        'is_wished': is_wished
    })

def live_search_api(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        # Tìm sách có tên HOẶC tác giả chứa từ khóa (không phân biệt hoa thường)
        # Giới hạn lấy 5 kết quả đầu tiên cho nhẹ Web
        books = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )[:5]
        
        results = []
        for book in books:
            # Xử lý cover_image an toàn (nếu dùng ImageField thì lấy .url, nếu dạng Text thì lấy thẳng)
            image_url = book.cover_image.url if hasattr(book.cover_image, 'url') else book.cover_image
            
            results.append({
                'id': book.id,
                'title': book.title,
                'author': book.author if book.author else 'Chưa rõ',
                'cover_image': image_url,
                'price': book.price,
                'url': reverse('book_detail', args=[book.id]) # Tự động tạo link chi tiết sách
            })
            
        return JsonResponse({'status': 'success', 'data': results})
        
    return JsonResponse({'status': 'empty', 'data': []})

@login_required
@require_POST
def api_add_review(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    rating = request.POST.get('rating')
    comment = request.POST.get('comment')

    if not rating or not comment:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập đủ thông tin.'})

    # Kiểm tra xem đã đánh giá chưa để tránh spam
    if Review.objects.filter(user=request.user, book=book).exists():
         return JsonResponse({'status': 'error', 'message': 'Bạn đã đánh giá sách này rồi.'})

    # Lưu đánh giá mới vào cơ sở dữ liệu
    review = Review.objects.create(
        user=request.user,
        book=book,
        rating=int(rating),
        comment=comment
    )

    # Chuẩn bị dữ liệu trả về cho Javascript vẽ giao diện
    # Lấy avatar (nếu có, không có thì dùng ảnh mặc định)
    avatar_url = request.user.avatar_url if hasattr(request.user, 'avatar_url') and request.user.avatar_url else '/static/img/user.jpg'
    full_name = request.user.get_full_name() or request.user.username
    
    # Tạo chuỗi ngôi sao
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

# Thêm vào cuối file views.py
def api_load_more_books(request):
    page = int(request.GET.get('page', 1))
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    sort = request.GET.get('sort', 'newest')
    
    # [ĐÃ THÊM]: Nhận diện cờ is_premium từ AJAX (Javascript) gửi lên
    is_premium = request.GET.get('is_premium', 'false')

    books_list = Book.objects.all()

    # [ĐÃ THÊM]: Nếu người dùng bấm Load More ở trang VIP thì chỉ lấy sách có phí
    if is_premium == 'true':
        books_list = books_list.filter(price__gt=0)

    # Lọc giống hệt hàm book_list
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

    # Lấy thông tin cá nhân hóa
    wishlist_ids = []
    borrowed_ids = []
    pending_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(user=request.user).values_list('book_id', flat=True))
        borrowed_ids = list(BorrowTransaction.objects.filter(user=request.user, status='BORROWED').values_list('book_id', flat=True))
        pending_ids = list(BorrowTransaction.objects.filter(user=request.user, status='PENDING').values_list('book_id', flat=True))

    paginator = Paginator(books_list, 6) # Mỗi lần Load More lấy 6 cuốn
    
    try:
        books = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})

    data = []
    for b in books:
        # Nhận diện trạng thái sách đối với user hiện tại
        if b.id in pending_ids: btn_status = 'PENDING'
        elif b.id in borrowed_ids: btn_status = 'BORROWED'
        elif b.quantity <= 0: btn_status = 'OUT_OF_STOCK'
        elif b.price and b.price > 0: btn_status = 'VIP'
        else: btn_status = 'AVAILABLE'

        # Xử lý ảnh an toàn
        image_url = b.cover_image.url if hasattr(b.cover_image, 'url') else b.cover_image

        data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author if b.author else 'Chưa rõ',
            'category_name': b.category.name if b.category else 'Khác', # Cung cấp thêm category name
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
    # Đếm số lượng thông báo chưa đọc của user hiện tại
    count = Notification.objects.filter(user=request.user, status='UNREAD').count()
    return JsonResponse({'status': 'success', 'unread_count': count})

# 2. HÀM API MỚI: Trả về thông báo khi cuộn trang
@login_required
def api_load_more_notifications(request):
    page = int(request.GET.get('page', 1))
    notifications_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifications_list, 8) # Mỗi lần cuộn tải thêm 8 cái
    
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
        
    # Đánh dấu đã đọc
    Notification.objects.filter(id__in=[n.id for n in notifications], status='UNREAD').update(status='READ')
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': notifications.has_next()})

# 2. HÀM API MỚI: Trả về lịch sử khi cuộn trang
@login_required
def api_load_more_history(request):
    page = int(request.GET.get('page', 1))
    history_list = BorrowTransaction.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(history_list, 8)
    
    try:
        history = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        return JsonResponse({'status': 'empty', 'data': [], 'has_next': False})
        
    data = []
    for item in history:
        cover_image = item.book.cover_image.url if hasattr(item.book.cover_image, 'url') else item.book.cover_image
        
        # Đóng gói dữ liệu JSON để gửi xuống JS
        data.append({
            'id': item.id,
            'book_title': item.book.title,
            'book_author': item.book.author or "Chưa rõ",
            'cover_image': cover_image,
            'borrow_date': item.borrow_date.strftime("%d/%m/%Y") if item.borrow_date else '-',
            'due_date': item.due_date.strftime("%d/%m/%Y") if item.due_date else '-',
            'return_date': item.return_date.strftime("%d/%m/%Y") if item.return_date else '-',
            'status': item.status,
            'is_late': getattr(item, 'is_late', False), # Lấy thuộc tính trả trễ
            'penalty_amount': getattr(item, 'penalty_amount', 0),
            'return_url': reverse('return_book', args=[item.id])
        })
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': history.has_next()})

# 2. HÀM API MỚI: Trả về sách yêu thích khi cuộn trang
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

    data = []
    for item in items:
        b = item.book
        
        # Nhận diện trạng thái nút mượn
        if b.id in pending_ids: btn_status = 'PENDING'
        elif b.id in borrowed_ids: btn_status = 'BORROWED'
        elif b.quantity <= 0: btn_status = 'OUT_OF_STOCK'
        elif b.price and b.price > 0: btn_status = 'VIP'
        else: btn_status = 'AVAILABLE'

        image_url = b.cover_image.url if hasattr(b.cover_image, 'url') else b.cover_image

        # Đóng gói dữ liệu giống hệt api_load_more_books để xài chung hàm JS
        data.append({
            'id': b.id,
            'title': b.title,
            'author': b.author or "Chưa rõ",
            'cover_image': image_url,
            'price': b.price,
            'quantity': b.quantity,
            'btn_status': btn_status,
            'is_wished': True, # Chắc chắn là True vì đang ở trang Yêu thích
            'url': reverse('book_detail', args=[b.id]),
            'borrow_url': reverse('borrow_book', args=[b.id]),
            'wishlist_api_url': reverse('api_toggle_wishlist', args=[b.id])
        })
        
    return JsonResponse({'status': 'success', 'data': data, 'has_next': items.has_next()})