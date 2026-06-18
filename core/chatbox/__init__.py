from datetime import timedelta
from django.utils import timezone
from core.models import BorrowTransaction, Notification
from .gemini_service import GeminiChatService

def check_and_create_due_reminders(user):
    if not user.is_authenticated:
        return

    # Kiểm tra hạn trả trong 2 ngày tới
    warning_date = timezone.now().date() + timedelta(days=2)
    
    # Quét dữ liệu dựa trên model của bạn
    nearing_due = BorrowTransaction.objects.filter(
        user=user,
        status='BORROWED',
        due_date=warning_date
    )

    for record in nearing_due:
        msg = f"⏰ Sắp hết hạn: Cuốn '{record.book.title}' cần được trả vào ngày {record.due_date.strftime('%d/%m/%Y')}."
        
        # Ngăn việc tạo thông báo trùng lặp mỗi khi load trang
        if not Notification.objects.filter(user=user, message=msg, type='REMINDER').exists():
            Notification.objects.create(
                user=user,
                message=msg,
                type='REMINDER',
                status='UNREAD'
            )

__all__ = ['check_and_create_due_reminders', 'GeminiChatService']

