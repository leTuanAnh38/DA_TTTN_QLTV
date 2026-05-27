# core/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

def check_overdue_job():
    """Quét sách trễ hạn (Chạy 1 lần/ngày)"""
    try:
        print("Đang chạy kiểm tra sách trễ hạn tự động...")
        call_command('check_overdue') 
    except Exception as e:
        logger.error(f"Lỗi khi chạy lệnh check_overdue: {e}")

def auto_cancel_job():
    """Quét hủy đơn không đến lấy (Chạy liên tục)"""
    try:
        call_command('auto_cancel') 
    except Exception as e:
        logger.error(f"Lỗi khi chạy lệnh auto_cancel: {e}")

def start():
    scheduler = BackgroundScheduler()
    
    # 1. Job cũ của bạn: Chạy lúc 8h sáng mỗi ngày
    scheduler.add_job(check_overdue_job, 'cron', hour=8, minute=0)
    
    # 2. JOB MỚI: Cứ mỗi 1 giờ sẽ tự động chạy ngầm 1 lần
    scheduler.add_job(auto_cancel_job, 'interval', minutes=1) 
    
    # (Mẹo: Nếu lúc đang code bạn muốn test xem nó có chạy không, 
    # hãy đổi 'interval', hours=1 thành 'interval', minutes=1 để nó chạy mỗi phút)
    
    scheduler.start()
    print("⏳ Hệ thống đặt lịch tự động đã khởi động (Có theo dõi đơn trễ giờ).")