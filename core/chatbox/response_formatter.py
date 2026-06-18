"""
Response formatter - tách logic format response để dễ tùy chỉnh
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FormattedResponse:
    """Represent a formatted response"""
    content: str
    type: str  # 'text', 'error', 'suggestion', 'confirmation'
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ResponseFormatter:
    """Base class cho response formatting"""
    
    def format_error(self, error_msg: str) -> FormattedResponse:
        """Format error message"""
        return FormattedResponse(
            content=f"❌ {error_msg}",
            type='error'
        )
    
    def format_success(self, msg: str) -> FormattedResponse:
        """Format success message"""
        return FormattedResponse(
            content=f"✅ {msg}",
            type='text'
        )
    
    def format_info(self, msg: str) -> FormattedResponse:
        """Format info message"""
        return FormattedResponse(
            content=f"ℹ️ {msg}",
            type='text'
        )
    
    def format_warning(self, msg: str) -> FormattedResponse:
        """Format warning message"""
        return FormattedResponse(
            content=f"⚠️ {msg}",
            type='text'
        )


class BookFormatter:
    """Format book-related responses"""
    
    @staticmethod
    def format_book_info(book, show_price: bool = True, show_quantity: bool = True) -> str:
        """Format book information"""
        info = f"'{book.title}' (Tác giả: {book.author or 'Đang cập nhật'}"
        
        if show_price:
            if book.price and book.price > 0:
                info += f" | 💰 {book.price:,.0f} VNĐ"
            else:
                info += " | ✨ Miễn phí"
        
        if show_quantity:
            info += f" | SL: {book.quantity}"
        
        info += ")"
        return info
    
    @staticmethod
    def format_book_list(books: List[Any], show_numbers: bool = True) -> str:
        """Format list of books"""
        if not books:
            return "Không có sách phù hợp."
        
        lines = []
        for i, book in enumerate(books, 1):
            prefix = f"{i}. " if show_numbers else "• "
            lines.append(prefix + BookFormatter.format_book_info(book))
        
        return "\n".join(lines)


class BorrowResponseFormatter:
    """Format borrow-related responses"""
    
    @staticmethod
    def format_borrow_confirmation(book: Any, pickup_date: str, shift: str) -> str:
        """Format borrow confirmation"""
        shift_display = "Sáng (07:30-11:30)" if shift == "SANG" else "Chiều (13:00-17:00)"
        price_part = ""
        
        if book.price and book.price > 0:
            price_part = f" Phí: {book.price:,.0f} VNĐ"
        
        return (f"✓ Đã đăng ký mượn '{book.title}'. "
                f"Nhận vào {shift_display} ngày {pickup_date}.{price_part}")
    
    @staticmethod
    def format_cannot_borrow(reason: str) -> str:
        """Format cannot borrow message"""
        return f"❌ Không thể mượn: {reason}"
    
    @staticmethod
    def format_borrow_options(books: List[Any]) -> str:
        """Format borrow options for user selection"""
        if len(books) == 1:
            return f"Tôi tìm thấy: {BookFormatter.format_book_info(books[0])}"
        
        book_list = BookFormatter.format_book_list(books)
        return f"Tôi tìm thấy vài cuốn sách phù hợp:\n{book_list}\n\nBạn muốn mượn cuốn nào? (Trả lời: 1, 2 hoặc 3)"
    
    @staticmethod
    def format_ask_datetime(book: Any, shift: Optional[str] = None) -> str:
        """Format ask for datetime message"""
        shift_text = "sáng hay chiều"
        if shift:
            shift_text = "sáng" if shift == "SANG" else "chiều"
        
        return (f"✅ Tôi sẽ giúp bạn mượn '{book.title}'. "
                f"Bạn muốn nhận vào buổi {shift_text} ngày nào?\n\n"
                f"💡 Ví dụ: sáng ngày 21/04/2026 hoặc ca chiều 21/04/2026")


class LibraryInfoFormatter:
    """Format library information and rules"""
    
    @staticmethod
    def format_user_status(user_status: Dict[str, Any]) -> str:
        """Format user library status"""
        return (
            f"📚 Trạng thái của bạn:\n"
            f"• Sách đang mượn: {user_status['active_borrows']}/4\n"
            f"• Có thể mượn thêm: {user_status['remaining_quota']} cuốn\n"
            f"• Tiền nợ: {user_status['fine']} VNĐ\n"
            f"• Có quyền mượn: {'✅ Được' if user_status['can_borrow'] else '❌ Bị chặn'}"
        )
    
    @staticmethod
    def format_borrow_rules() -> str:
        """Format borrowing rules"""
        return (
            "📖 Quy tắc mượn sách:\n"
            "• Mượn tối đa: 4 cuốn/người\n"
            "• Thời hạn: 14 ngày/cuốn\n"
            "• Trễ hạn: Phạt 5.000 VNĐ/ngày + 5 điểm trừ\n"
            "• Mất sách: Đền 100% giá sách"
        )
    
    @staticmethod
    def format_late_fee_info(days_late: int, fee_per_day: int) -> str:
        """Format late fee information"""
        total_fee = days_late * fee_per_day
        return (
            f"⚠️ Sách trễ {days_late} ngày\n"
            f"• Phạt: {fee_per_day:,} VNĐ/ngày × {days_late} ngày = {total_fee:,} VNĐ\n"
            f"• Điểm trừ: 5 điểm/ngày"
        )


class ResponseBuilder:
    """Builder pattern cho tạo complex responses"""
    
    def __init__(self):
        self.parts: List[str] = []
        self.metadata: Dict[str, Any] = {}
    
    def add_header(self, text: str) -> 'ResponseBuilder':
        """Add header"""
        self.parts.append(f"\n### {text}")
        return self
    
    def add_line(self, text: str, indent: int = 0) -> 'ResponseBuilder':
        """Add line"""
        self.parts.append("  " * indent + text)
        return self
    
    def add_section(self, title: str, content: str) -> 'ResponseBuilder':
        """Add section"""
        self.parts.append(f"\n**{title}:**\n{content}")
        return self
    
    def add_separator(self) -> 'ResponseBuilder':
        """Add separator"""
        self.parts.append("\n" + "-" * 40 + "\n")
        return self
    
    def add_meta(self, key: str, value: Any) -> 'ResponseBuilder':
        """Add metadata"""
        self.metadata[key] = value
        return self
    
    def build(self, response_type: str = 'text') -> FormattedResponse:
        """Build final response"""
        content = "\n".join(self.parts).strip()
        return FormattedResponse(
            content=content,
            type=response_type,
            metadata=self.metadata
        )
