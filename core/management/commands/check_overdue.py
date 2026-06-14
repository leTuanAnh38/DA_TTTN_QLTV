from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
# Đã sửa BorrowRecord thành BorrowTransaction
from core.models import BorrowTransaction, Notification 

class Command(BaseCommand):
    help = 'Quét các đơn mượn trễ hạn, tạo thông báo web và gửi email'

    def handle(self, *args, **kwargs):
        today = timezone.localtime().date()
        
        # 1. Tìm các sách đang mượn (BORROWED) và ngày trả < hôm nay
        overdue_records = BorrowTransaction.objects.filter(
            status='BORROWED', 
            due_date__lt=today
        )

        count = 0
        for record in overdue_records:
            user = record.user
            book = record.book
            
            # --- TẠO THÔNG BÁO IN-APP TRÊN WEB ---
            Notification.objects.create(
                user=user,
                message=f"Sách '{book.title}' đã quá hạn trả ({record.due_date}). Vui lòng trả sách ngay để tránh bị phạt!",
                type='WARNING' 
            )

            # --- GỬI EMAIL THÔNG BÁO ---
            if user.email:
                subject = '[Thư Viện] Thông báo sách quá hạn'
                message = (
                    f"Chào {user.first_name or user.username},\n\n"
                    f"Chúng tôi thông báo cuốn sách '{book.title}' bạn mượn đã hết hạn vào ngày {record.due_date}.\n"
                    f"Vui lòng mang sách đến thư viện để hoàn trả hoặc gia hạn trong thời gian sớm nhất.\n\n"
                    f"Trân trọng,\nĐội ngũ Quản lý Thư viện."
                )
                try:
                    send_mail(
                        subject,
                        message,
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Lỗi khi gửi email cho {user.email}: {e}'))

            # Đã mở comment: Tự động đổi trạng thái đơn mượn thành Quá Hạn
            record.status = 'OVERDUE'
            record.save()
            
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Hoàn tất! Đã gửi cảnh báo và cập nhật trạng thái cho {count} đơn trễ hạn.'))