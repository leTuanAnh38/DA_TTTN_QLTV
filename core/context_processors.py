from .models import BorrowTransaction, Wishlist, Category, Notification # Thêm Notification vào đây
from django.db.models.functions import ExtractMonth
from django.db.models import Count
from core.models import Cart
def dashboard_stats(request):
    # Lấy dữ liệu mượn sách theo tháng
    stats = BorrowTransaction.objects.annotate(month=ExtractMonth('borrow_date')) \
        .values('month').annotate(count=Count('id')).order_by('month')
    
    # Khởi tạo mảng 12 tháng với giá trị 0
    data = [0] * 12
    for s in stats:
        if s['month']:
            data[s['month'] - 1] = s['count']
            
    return {'borrow_stats': data}

def global_counts(request):
    # Lấy toàn bộ danh mục sách từ CSDL
    categories = Category.objects.all()
    
    # Đếm số sách yêu thích
    wishlist_count = 0
    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        
    return {
        'wishlist_count': wishlist_count,
        'categories': categories
    }


def notifications_count(request):
    """Đếm số lượng thông báo chưa đọc cho toàn bộ website"""
    if request.user.is_authenticated:
        # Lọc theo đúng trạng thái 'UNREAD' trong model của Khanh
        count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}


def show_borrow_info(request):
    """Provide a one-time borrow/payment informational message stored in session.
    The view should set `request.session['show_borrow_info_msg'] = '...message...'` before redirecting.
    This processor pops the value so the message is shown only once.
    """
    msg = ''
    try:
        msg = request.session.pop('show_borrow_info_msg') if 'show_borrow_info_msg' in request.session else ''
    except Exception:
        msg = ''
    return {'show_borrow_info_msg': msg}
def cart_count(request):
    if request.user.is_authenticated:
        # Lấy giỏ hàng của user từ Database
        user_cart = Cart.objects.filter(user=request.user).first()
        if user_cart:
            return {'global_cart_count': user_cart.items.count()}
    return {'global_cart_count': 0}