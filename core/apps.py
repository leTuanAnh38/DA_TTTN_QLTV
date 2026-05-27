from django.apps import AppConfig
import os
from django.core.management import call_command
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Quản lý Thư viện'

    def ready(self):
        # Mẹo nhỏ: Dùng 'RUN_MAIN' để ngăn Django chạy code 2 lần (do tính năng tự động reload code của runserver)
        if os.environ.get('RUN_MAIN') == 'true':
            
            # 1. Bật hệ thống đếm giờ chạy ngầm (để tự chạy lúc 8h sáng các ngày sau)
            from . import scheduler
            scheduler.start()

            # 2. ÉP HỆ THỐNG QUÉT NGAY LẬP TỨC MỘT LẦN VÀO LÚC BẬT SERVER
            try:
                print("=================================================")
                print(" Đang quét tìm sách quá hạn ngay lập tức...")
                call_command('check_overdue')
                print(" Quét xong! Đã cập nhật và gửi thông báo nếu có.")
                print("=================================================")
            except Exception as e:
                print(f"Lỗi khi quét: {e}")