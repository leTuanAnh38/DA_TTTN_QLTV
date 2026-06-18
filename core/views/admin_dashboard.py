from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db.models import Count
from core.models import Book, BorrowTransaction
from django.db.models import Sum # BẮT BUỘC PHẢI THÊM DÒNG NÀY Ở ĐẦU FILE

class AdminDashboardView(TemplateView):
    template_name = 'admin/custom_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Ô 1: TỔNG SÁCH TRONG THƯ VIỆN (Dùng cột initial_quantity)
        total_q = Book.objects.aggregate(total=Sum('initial_quantity'))['total']
        context['total_books'] = total_q if total_q else 0
        
        # Ô 2: SÁCH ĐANG TRÊN KỆ (Dùng cột quantity - số lượng còn lại)
        avail_q = Book.objects.aggregate(total=Sum('quantity'))['total']
        context['available_books'] = avail_q if avail_q else 0
        
        # Các ô còn lại
        context['pending_transactions'] = BorrowTransaction.objects.filter(status='PENDING')
        context['overdue_transactions'] = BorrowTransaction.objects.filter(status='OVERDUE')
        
        return context

@staff_member_required
def admin_chart_api(request):
    # API vẽ biểu đồ
    status_data = [
        BorrowTransaction.objects.filter(status='BORROWED').count(),
        BorrowTransaction.objects.filter(status='PENDING').count(),
        BorrowTransaction.objects.filter(status='RETURNED').count(),
        BorrowTransaction.objects.filter(status='OVERDUE').count(),
    ]
    
    top_books = Book.objects.annotate(num_borrows=Count('borrow_records')).order_by('-num_borrows')[:5]
    
    return JsonResponse({
        "status_labels": ['Đang mượn', 'Chờ duyệt', 'Đã trả', 'Quá hạn'],
        "status_data": status_data,
        "top_labels": [b.title[:15] + "..." for b in top_books],
        "top_data": [b.num_borrows for b in top_books],
    })