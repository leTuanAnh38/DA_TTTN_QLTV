# file: core/views/borrow_views.py
from django.http import JsonResponse
from django.urls import reverse
from datetime import timedelta, datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Case, When, Value, IntegerField,F
from core.models import Cart, CartItem
from core.models import Book, BorrowTransaction, Notification

# ==========================================
# 1. NGHIỆP VỤ MƯỢN SÁCH
# ==========================================
def borrow_book(request, book_id):
    # CHÈN THÊM: Kiểm tra đăng nhập thủ công để trả JSON cho AJAX
    if not request.user.is_authenticated:
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        if is_ajax:
            return JsonResponse({
                'status': 'warning', 
                'message': 'Vui lòng đăng nhập để mượn sách!', 
                'redirect': reverse('login')
            })
        return redirect('login')

    user = request.user
    # 1. NHẬN DIỆN AJAX: Kiểm tra xem yêu cầu có phải gửi ngầm không
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    # Hàm hỗ trợ: AJAX thì trả JSON, bình thường thì Redirect kèm thông báo Django
    def respond(status, message, redirect_url=None):
        if is_ajax:
            return JsonResponse({'status': status, 'message': message, 'redirect': redirect_url})
        else:
            if status == 'error': messages.error(request, message)
            elif status == 'warning': messages.warning(request, message)
            else: messages.success(request, message)
            return redirect(redirect_url or request.META.get('HTTP_REFERER', 'book_list'))

    if user.total_fine > 0:
        return respond('error', f"Bạn đang nợ ({user.total_fine} VNĐ) tiền phạt. Vui lòng thanh toán trước!", reverse('profile'))

    overdue_count = BorrowTransaction.objects.filter(user=user, status='OVERDUE').count()
    if overdue_count > 0:
        return respond('error', f"Bạn có {overdue_count} cuốn sách đang QUÁ HẠN. Vui lòng trả sách và nộp phạt (nếu có) trước khi mượn sách mới!", reverse('borrow_history'))

    if not getattr(user, 'msv', None) or not getattr(user, 'lop', None):
        return respond('warning', "Vui lòng cập nhật MSSV và Lớp trong hồ sơ trước khi mượn sách!", reverse('profile'))

    active_borrows_count = BorrowTransaction.objects.filter(
        user=user,
        status__in=['PENDING', 'BORROWED', 'OVERDUE']
    ).count()

    max_books = user.rank_info['max_books']
    if active_borrows_count >= max_books:
        return respond('error', f"Bạn đang mượn hoặc chờ duyệt {active_borrows_count} cuốn rồi. Với hạng {user.rank_info['level']}, bạn chỉ được mượn tối đa {max_books} cuốn!")

    book = get_object_or_404(Book, id=book_id)
    #KIỂM TRA MƯỢN TRÙNG
    already_borrowed = BorrowTransaction.objects.filter(
        user=user, 
        book=book, 
        status__in=['PENDING', 'BORROWED', 'OVERDUE']
    ).exists()

    if already_borrowed:
        return respond('warning', f"Bạn đang mượn hoặc đã gửi yêu cầu mượn cuốn '{book.title}' rồi!")
    
    if book.quantity <= 0:
        return respond('error', f"Sách '{book.title}' đã hết trong kho!")
        
    # LẤY DỮ LIỆU TỪ FORM (Ngày, Ca lấy, Phương thức thanh toán)
    is_premium = book.price and book.price > 0
    if request.method == 'POST':
        pickup_date = request.POST.get('pickup_date')
        pickup_shift = request.POST.get('pickup_shift')
        payment_method = request.POST.get('payment_method', 'FREE')
        
        if not pickup_date or not pickup_shift:
            return respond('error', "Vui lòng chọn ngày và ca lấy sách!")
        # ---------- THÊM ĐOẠN LOGIC CHẶN GIỜ NÀY ----------
        pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d').date()
        today = timezone.localtime().date()
        current_hour = timezone.localtime().hour
        
        if pickup_date_obj == today:
            if pickup_shift == 'SANG' and current_hour >= 11:
                return respond('error', "Ca Sáng hôm nay đã kết thúc. Vui lòng chọn ca Chiều hoặc ngày khác!")
            if pickup_shift == 'CHIEU' and current_hour >= 17:
                return respond('error', "Các ca nhận sách hôm nay đã kết thúc. Vui lòng chọn ngày khác!")
    else:
        return respond('error', "Vui lòng sử dụng form đăng ký để chọn thời gian nhận sách.")

    pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d').date()
    han_tra = pickup_date_obj + timedelta(days=14)
    status = 'PENDING' 
    is_paid = False if is_premium else True

    # Xử lý chuỗi thông báo thời gian
    try:
        formatted_date = datetime.strptime(pickup_date, '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        formatted_date = pickup_date
    shift_display = "Buổi Sáng (07:30 - 11:30)" if pickup_shift == 'SANG' else "Buổi Chiều (13:00 - 17:00)"

    # 9. TIẾN HÀNH TẠO GIAO DỊCH
    try:
        with db_transaction.atomic():
            BorrowTransaction.objects.create(
                user=user, book=book, due_date=han_tra, 
                status=status, payment_method=payment_method, is_paid=is_paid,
                pickup_date=pickup_date, pickup_shift=pickup_shift 
            )

            # Tùy chỉnh tin nhắn theo loại sách
            if is_premium:
                payment_display = dict(BorrowTransaction.PAYMENT_CHOICES).get(payment_method, payment_method)
                msg = f"Đăng ký thành công! Vui lòng thanh toán {book.price:,.0f} VNĐ ({payment_display}) và đến nhận sách vào {shift_display} ngày {formatted_date}."
            else:
                msg = f"Đăng ký thành công! Bạn nhớ đến nhận sách vào {shift_display} ngày {formatted_date}. Quá hạn hệ thống sẽ tự hủy đơn!"

            Notification.objects.create(user=user, message=msg, type='SYSTEM', status='UNREAD')
            book.quantity -= 1
            book.save()

        if not is_ajax:
            try:
                request.session['show_borrow_info_msg'] = msg
            except Exception:
                pass

        return respond('success', msg)
    except Exception as e:
        return respond('error', f"Lỗi hệ thống: {str(e)}")
# ==========================================
# 2. HỆ THỐNG GIỎ MƯỢN SÁCH (CART)
# ==========================================
def add_to_cart(request, book_id):
    # 0. Kiểm tra đăng nhập (Trả về JSON cho AJAX xử lý)
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False, 
            'message': 'Vui lòng đăng nhập để thêm sách vào giỏ!',
            'redirect': reverse('login')
        })

    # 1. Lấy hoặc tạo giỏ hàng cho user
    user_cart, created = Cart.objects.get_or_create(user=request.user)
    
    # 2. Kiểm tra giới hạn số lượng (Dựa trên Hạng)
    max_books = request.user.rank_info['max_books']
    active_borrows = BorrowTransaction.objects.filter(user=request.user, status__in=['PENDING', 'BORROWED', 'OVERDUE']).count()
    items_in_cart = user_cart.items.count()
    
    if active_borrows + items_in_cart >= max_books:
        return JsonResponse({
            'success': False, 
            'message': f'Giới hạn {max_books} cuốn! Hạng {request.user.rank_info["level"]} của bạn đang giữ {active_borrows} cuốn và có {items_in_cart} cuốn trong giỏ.'
        })
        
    # 3. Kiểm tra mượn trùng trong lịch sử
    already_borrowed = BorrowTransaction.objects.filter(user=request.user, book_id=book_id, status__in=['PENDING', 'BORROWED', 'OVERDUE']).exists()
    if already_borrowed:
        return JsonResponse({'success': False, 'message': 'Bạn đã mượn hoặc đang chờ duyệt cuốn sách này rồi.'})

    # 4. Kiểm tra xem sách đã có trong giỏ chưa
    book = get_object_or_404(Book, id=book_id)
    item, created_item = CartItem.objects.get_or_create(cart=user_cart, book=book)
    
    if created_item:
        return JsonResponse({'success': True, 'cart_count': user_cart.items.count(), 'message': 'Đã thêm vào giỏ sách!'})
    else:
        return JsonResponse({'success': False, 'message': 'Sách này đã có trong giỏ.'})

@login_required(login_url='login')
def view_cart(request):
    # Lấy giỏ hàng và danh sách sách bên trong
    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = user_cart.items.select_related('book').all()
    
    books = [item.book for item in cart_items]
    total_fee = sum(book.price for book in books if book.price)
    
    return render(request, 'core/user/cart.html', {'books': books, 'total_fee': total_fee})

@login_required(login_url='login')
def remove_from_cart(request, book_id):
    # Xóa sách khỏi database
    CartItem.objects.filter(cart__user=request.user, book_id=book_id).delete()
    messages.success(request, "Đã xóa sách khỏi giỏ.")
    return redirect('view_cart')

@login_required(login_url='login')
def checkout_cart(request):
    if request.method == 'POST':
        user_cart = Cart.objects.filter(user=request.user).first()
        if not user_cart or not user_cart.items.exists():
            return redirect('book_list')
        
        # THÊM: Chặn checkout nếu có sách quá hạn
        overdue_count = BorrowTransaction.objects.filter(user=request.user, status='OVERDUE').count()
        if overdue_count > 0:
            messages.error(request, f"Bạn đang có {overdue_count} cuốn sách QUÁ HẠN trả. Vui lòng trả sách trước khi mượn thêm!")
            return redirect('borrow_history')
            
        pickup_date = request.POST.get('pickup_date')
        pickup_shift = request.POST.get('pickup_shift')
        payment_method = request.POST.get('payment_method', 'FREE')
        
        # 1. Bắt lỗi nếu người dùng cố tình can thiệp HTML bỏ chọn ngày/ca
        if not pickup_date or not pickup_shift:
            messages.error(request, "Vui lòng chọn ngày và ca lấy sách!")
            return redirect('view_cart')

        try:
            pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Định dạng ngày không hợp lệ!")
            return redirect('view_cart')

        # ---------- 2. LOGIC CHẶN GIỜ QUÁ HẠN ----------
        today = timezone.localtime().date()
        current_hour = timezone.localtime().hour
        
        if pickup_date_obj == today:
            if pickup_shift == 'SANG' and current_hour >= 11:
                messages.error(request, "Ca Sáng hôm nay đã kết thúc. Vui lòng chọn ca Chiều hoặc ngày khác!")
                return redirect('view_cart')
            
            if pickup_shift == 'CHIEU' and current_hour >= 17:
                messages.error(request, "Các ca nhận sách hôm nay đã kết thúc. Vui lòng chọn ngày kế tiếp!")
                return redirect('view_cart')

        # ---------- 3. KIỂM TRA GIỚI HẠN SỐ LƯỢNG (DỰA TRÊN HẠNG) ----------
        active_borrows_count = BorrowTransaction.objects.filter(
            user=request.user,
            status__in=['PENDING', 'BORROWED', 'OVERDUE']
        ).count()
        
        max_books = request.user.rank_info['max_books']
        cart_count = user_cart.items.count()
        
        if active_borrows_count + cart_count > max_books:
            messages.error(request, f"Bạn đang mượn/chờ duyệt {active_borrows_count} cuốn. Giỏ hàng có {cart_count} cuốn. Tổng cộng vượt quá giới hạn {max_books} cuốn của hạng {request.user.rank_info['level']}!")
            return redirect('view_cart')

        cart_items = user_cart.items.all()
        han_tra = pickup_date_obj + timedelta(days=14)
        
        try:
            with db_transaction.atomic():
                count = 0
                total_fee = 0
                for item in cart_items:
                    book = item.book
                    if book.quantity > 0:
                        is_premium = book.price and book.price > 0
                        BorrowTransaction.objects.create(
                            user=request.user, book=book, due_date=han_tra, status='PENDING',
                            payment_method=payment_method, is_paid=not is_premium,
                            pickup_date=pickup_date, pickup_shift=pickup_shift
                        )
                        book.quantity -= 1
                        book.save()
                        total_fee += book.price if book.price else 0
                        count += 1
                
                cart_items.delete()
                shift_display = "Sáng" if pickup_shift == 'SANG' else "Chiều"
                # Định dạng lại chuỗi ngày hiển thị trong thông báo cho đẹp (DD/MM/YYYY)
                display_date = pickup_date_obj.strftime('%d/%m/%Y')
                
                msg = f"Đăng ký {count} cuốn thành công! Nhớ đến lấy sách vào ca {shift_display} ngày {display_date}."
                Notification.objects.create(user=request.user, message=msg, type='SYSTEM', status='UNREAD')
                
            messages.success(request, msg)
            return redirect('borrow_history')
        except Exception as e:
            messages.error(request, f"Lỗi hệ thống: {str(e)}")
            return redirect('view_cart')
            
    return redirect('view_cart')
# ==========================================
# 2. LỊCH SỬ GIAO DỊCH
# ==========================================
@login_required(login_url='login')
def borrow_history(request):
    history_list = BorrowTransaction.objects.filter(user=request.user).annotate(
        status_priority=Case(
            When(status='OVERDUE', then=Value(1)),   
            When(status='BORROWED', then=Value(2)), 
            When(status='PENDING', then=Value(3)),
            When(status__in=['RETURNED', 'CANCELLED'], then=Value(4)),  # Nhóm các đơn đã kết thúc (Trả/Hủy) vào cùng mức
            default=Value(5),
            output_field=IntegerField(),
        )
    ).order_by('status_priority', '-updated_at')
    
    # Phân trang: Mỗi lần tải 8 giao dịch
    paginator = Paginator(history_list, 8) 
    page = request.GET.get('page', 1)
    
    try:
        history = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        history = paginator.page(1)
        
    return render(request, 'core/user/borrow_history.html', {'history': history})
# ==========================================
# 3. NGHIỆP VỤ YÊU CẦU TRẢ SÁCH (Dành cho Sinh viên)
# ==========================================
@login_required(login_url='login')
def return_book(request, transaction_id):
    borrow_record = get_object_or_404(BorrowTransaction, id=transaction_id, user=request.user, status__in=['BORROWED', 'OVERDUE'])
    
    try:
        #  Tính toán trễ hạn tạm tính
        today = timezone.localtime().date()
        late_info = ""
        if today > borrow_record.due_date:
            days_late = (today - borrow_record.due_date).days
            estimated_fine = days_late * 5000  
            late_info = f" (CẢNH BÁO: Bạn đã trễ {days_late} ngày, phí phạt dự kiến là {estimated_fine:,.0f} VNĐ)"

        borrow_record.status = 'PENDING'
        borrow_record.reason = 'YÊU CẦU TRẢ' 
        borrow_record.save()
        
        msg = f"Yêu cầu trả cuốn '{borrow_record.book.title}' đã được gửi.{late_info} Vui lòng mang sách đến quầy trong vòng 24h(ca sáng - chiều) để Thủ thư xác nhận tình trạng vật lý và chốt phí phạt cuối cùng."
        
        Notification.objects.create(
            user=request.user, 
            message=msg, 
            type='WARNING' if late_info else 'SYSTEM', 
            status='UNREAD'
        )
        
        # Hiển thị thông báo màu vàng nếu có phí phạt, màu xanh nếu trả đúng hạn
        if late_info:
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    except Exception as e:
        messages.error(request, f"Đã xảy ra lỗi: {str(e)}")
        
    return redirect('borrow_history')


@login_required(login_url='login')
def return_books_batch(request):
    """Xử lý yêu cầu trả nhiều sách cùng lúc"""
    if request.method == 'POST':
        transaction_ids = request.POST.getlist('transaction_ids')
        
        if not transaction_ids:
            messages.warning(request, "Bạn chưa chọn cuốn sách nào để trả.")
            return redirect('borrow_history')

        records = BorrowTransaction.objects.filter(
            id__in=transaction_ids,
            user=request.user,
            status__in=['BORROWED', 'OVERDUE']
        )

        count = records.count()
        if count > 0:
            # 1. Tính toán tổng phí phạt dự kiến cho cả lô sách
            today = timezone.localtime().date()
            total_estimated_fine = 0
            late_count = 0
            
            for r in records:
                if today > r.due_date:
                    days_late = (today - r.due_date).days
                    total_estimated_fine += days_late * 5000
                    late_count += 1
            
            late_info = ""
            if total_estimated_fine > 0:
                late_info = f" (Phát hiện {late_count} cuốn trễ hạn, tổng phí phạt dự kiến: {total_estimated_fine:,.0f} VNĐ)"

            # 2. Cập nhật trạng thái hàng loạt
            records.update(status='PENDING', reason='YÊU CẦU TRẢ')
            
            msg = f"Đã gửi yêu cầu báo trả cho {count} cuốn sách.{late_info} Vui lòng mang sách đến quầy trong vòng 24h(ca sáng - chiều) để Thủ thư kiểm tra."
            
            Notification.objects.create(
                user=request.user, 
                message=msg, 
                type='WARNING' if total_estimated_fine > 0 else 'SYSTEM', 
                status='UNREAD'
            )
            
            if total_estimated_fine > 0:
                messages.warning(request, msg)
            else:
                messages.success(request, msg)
        else:
            messages.error(request, "Không có giao dịch nào hợp lệ để trả.")

    return redirect('borrow_history')
# ==========================================
# 4. GIA HẠN SÁCH
# ==========================================
@login_required(login_url='login')
def renew_book(request, transaction_id):
    trans = get_object_or_404(BorrowTransaction, id=transaction_id, user=request.user)
    today = timezone.localtime().date()

    # 1. Check: Sách phải đang mượn
    if trans.status != 'BORROWED':
        messages.error(request, "Chỉ có thể gia hạn những cuốn sách đang trong thời gian mượn.")
        return redirect('borrow_history')

    # 2. Check: Không cho phép gia hạn sách trễ hạn
    if today > trans.due_date:
        messages.error(request, "Sách đã quá hạn! Không thể gia hạn, vui lòng trả sách và nộp phạt.")
        return redirect('borrow_history')

    # 3. Check: Số lần gia hạn tối đa (2 lần)
    if trans.renewal_count >= 2:
        messages.error(request, "Bạn đã sử dụng hết lượt gia hạn cho cuốn sách này (Tối đa 2 lần).")
        return redirect('borrow_history')

    # 4. Check: Chỉ cho phép gia hạn khi còn <= 2 ngày nữa là đến hạn
    days_until_due = (trans.due_date - today).days
    if days_until_due > 2:
        messages.warning(request, f"Chưa thể gia hạn! Bạn chỉ được phép gia hạn trước ngày hết hạn 1-2 ngày (Hiện còn {days_until_due} ngày nữa).")
        return redirect('borrow_history')

    try:
        trans.due_date = trans.due_date + timedelta(days=7)
        trans.renewal_count += 1
        trans.save()

        msg = f"Gia hạn thành công! Hạn trả mới của cuốn '{trans.book.title}' là {trans.due_date.strftime('%d/%m/%Y')}. (Đã gia hạn {trans.renewal_count}/2 lần)."
        
        Notification.objects.create(
            user=request.user, message=msg, type='SYSTEM', status='UNREAD'
        )
        messages.success(request, msg)
        
    except Exception as e:
        messages.error(request, f"Đã xảy ra lỗi: {str(e)}")

    return redirect('borrow_history')