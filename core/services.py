# core/services.py
from datetime import timedelta
from django.utils import timezone
from .models import BorrowTransaction, Notification 

def check_and_create_due_reminders(user):
    if not user.is_authenticated:
        return

    today = timezone.now().date()

    # ====================================================
    # 1. NHẮC NHỞ SẮP HẾT HẠN (Trước 2 ngày)
    # ====================================================
    warning_date = today + timedelta(days=2)
    nearing_due = BorrowTransaction.objects.filter(
        user=user,
        status='BORROWED',
        due_date=warning_date
    )

    for record in nearing_due:
        msg = f"⏰ Sắp hết hạn: Cuốn '{record.book.title}' cần được trả vào ngày {record.due_date.strftime('%d/%m/%Y')}."
        
        # Ngăn việc tạo thông báo trùng lặp
        if not Notification.objects.filter(user=user, message=msg, type='REMINDER').exists():
            Notification.objects.create(
                user=user,
                message=msg,
                type='REMINDER',
                status='UNREAD'
            )

    # ====================================================
    # 2. CẢNH BÁO QUÁ HẠN KÈM SỐ NGÀY TRỄ (MỚI THÊM)
    # ====================================================
    # Quét tất cả các đơn đang trong trạng thái QUÁ HẠN
    overdue_records = BorrowTransaction.objects.filter(
        user=user,
        status='OVERDUE'
    )

    for record in overdue_records:
        if today > record.due_date:
            days_late = (today - record.due_date).days
            estimated_fine = days_late * 5000  # Đơn giá 5000đ/ngày
            
            # Tạo chuỗi thông báo chứa chính xác số ngày trễ hôm nay
            msg_overdue = f"🚨 QUÁ HẠN: Cuốn '{record.book.title}' đã trễ {days_late} ngày. Phạt dự kiến: {estimated_fine:,.0f}đ. Vui lòng mang sách trả ngay!"
            
            # Kiểm tra xem hôm nay đã gửi thông báo có nội dung y hệt thế này chưa (để tránh spam mỗi lần f5 web)
            if not Notification.objects.filter(user=user, message=msg_overdue, type='WARNING').exists():
                Notification.objects.create(
                    user=user,
                    message=msg_overdue,
                    type='WARNING',
                    status='UNREAD'
                )