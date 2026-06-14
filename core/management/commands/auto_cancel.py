# core/management/commands/auto_cancel.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction as db_transaction
from core.models import BorrowTransaction, Notification

class Command(BaseCommand):
    help = 'Tự động hủy lịch hẹn mượn và yêu cầu trả sách ảo'

    def handle(self, *args, **kwargs):
        now = timezone.localtime()
        today_date = now.date()
        current_hour = now.hour

        count_cancel_borrow = 0
        count_cancel_return = 0

        # ========================================================
        # NHIỆM VỤ 1: HỦY ĐƠN MƯỢN KHÔNG TỚI LẤY
        # ========================================================
        pending_mmuon = BorrowTransaction.objects.filter(status='PENDING').exclude(reason='YÊU CẦU TRẢ')
        
        for t in pending_mmuon:
            is_expired = False
            if t.pickup_date:
                if t.pickup_date < today_date:
                    is_expired = True
                elif t.pickup_date == today_date:
                    if t.pickup_shift == 'SANG' and current_hour >= 12:
                        is_expired = True
                    elif t.pickup_shift == 'CHIEU' and current_hour >= 17:
                        is_expired = True

            if is_expired:
                with db_transaction.atomic():
                    t.status = 'CANCELLED'
                    t.reason = 'Hủy tự động do quá hạn thời gian đến nhận sách'
                    t.save()
                    
                    t.book.quantity += 1
                    t.book.save()
                    
                    shift_text = "Sáng" if t.pickup_shift == 'SANG' else "Chiều"
                    cancel_msg = f"HỦY TỰ ĐỘNG: Đơn mượn '{t.book.title}' bị hủy do không đến nhận (Ca {shift_text} ngày {t.pickup_date.strftime('%d/%m/%Y')})."
                    Notification.objects.create(user=t.user, message=cancel_msg, type='SYSTEM', status='UNREAD')
                    count_cancel_borrow += 1

        # ========================================================
        # NHIỆM VỤ 2: HỦY ĐƠN "YÊU CẦU TRẢ" ẢO (SAU 24H)
        # ========================================================
        return_requests = BorrowTransaction.objects.filter(status='PENDING', reason='YÊU CẦU TRẢ')
        
        for r in return_requests:
            # Nếu thời gian từ lúc bấm nút (updated_at) đến hiện tại lớn hơn 1 ngày
            if r.updated_at < now - timedelta(days=1):
                with db_transaction.atomic():
                    # Kiểm tra xem hạn trả đã qua chưa để gán đúng trạng thái
                    if r.due_date < today_date:
                        r.status = 'OVERDUE'
                    else:
                        r.status = 'BORROWED'
                        
                    r.reason = '' # Xóa nhãn yêu cầu trả
                    r.save()
                    
                    cancel_msg = f"HỦY TỰ ĐỘNG: Yêu cầu trả sách '{r.book.title}' bị hủy do quá 24h bạn không mang sách tới quầy. Sách quay về trạng thái Đang mượn."
                    Notification.objects.create(user=r.user, message=cancel_msg, type='SYSTEM', status='UNREAD')
                    count_cancel_return += 1
                    
        # Báo cáo tổng kết ra Terminal
        self.stdout.write(self.style.SUCCESS(
            f'[{now.strftime("%H:%M:%S")}] Quét xong! Hủy {count_cancel_borrow} lịch mượn, Hoàn tác {count_cancel_return} yêu cầu trả ảo.'
        ))