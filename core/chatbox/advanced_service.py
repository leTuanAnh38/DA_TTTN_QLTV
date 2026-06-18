"""
Refactored Gemini Chat Service - using modular architecture
Các file cũ vẫn hoạt động, file này là version nâng cấp
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import re

from django.conf import settings
from django.db.models import Q, Count
from django.utils import timezone

from core.models import Book, User, BorrowTransaction, Notification, Category

from .config import ChatConfig, get_config_from_settings
from .cache_backend import CacheBackend, CacheManager
from .llm_client import LLMClient, LLMClientFactory, Message
from .intent_handler import IntentRegistry, IntentResult
from .response_formatter import (
    ResponseFormatter, BookFormatter, BorrowResponseFormatter,
    LibraryInfoFormatter, ResponseBuilder, FormattedResponse
)
from .error_handler import ErrorHandler, ChatServiceError, APIError

logger = logging.getLogger(__name__)


class AdvancedGeminiChatService:
    """
    Nâng cấp version của GeminiChatService với modular architecture
    
    Features:
    - Pluggable intent handlers
    - Abstracted cache backend (django/redis/memory)
    - Abstracted LLM client (Gemini/OpenAI/Anthropic)
    - Better error handling
    - Response formatting system
    - Type hints
    """
    
    def __init__(
        self,
        config: Optional[ChatConfig] = None,
        cache_backend: Optional[CacheBackend] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize Advanced Chat Service"""
        
        # Load configuration
        self.config = config or get_config_from_settings(settings)
        logger.info(f"[CHAT] Initialized with config: {self.config.to_dict()}")
        
        # Setup cache backend
        self.cache = cache_backend or self._setup_cache()
        logger.info(f"[CHAT] Using cache backend: {self.config.CACHE_BACKEND}")
        
        # Setup LLM client
        self.llm_client = llm_client or self._setup_llm_client()
        
        # Setup intent registry
        self.intent_registry = IntentRegistry()
        
        # Setup formatters
        self.response_formatter = ResponseFormatter()
        self.book_formatter = BookFormatter()
        self.borrow_formatter = BorrowResponseFormatter()
        self.library_formatter = LibraryInfoFormatter()
        
        # Setup error handler
        self.error_handler = ErrorHandler()
    
    def _setup_cache(self) -> CacheBackend:
        """Setup cache backend"""
        try:
            return CacheManager.create_backend(
                self.config.CACHE_BACKEND
            )
        except Exception as e:
            logger.warning(f"Failed to setup {self.config.CACHE_BACKEND} cache, falling back to memory: {e}")
            return CacheManager.create_backend('memory')
    
    def _setup_llm_client(self) -> LLMClient:
        """Setup LLM client"""
        try:
            api_key = settings.GEMINI_API_KEY
            return LLMClientFactory.create(
                provider='gemini',
                api_key=api_key,
                model=self.config.GEMINI_MODEL,
                rate_limit=self.config.RATE_LIMIT_SECONDS
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise ChatServiceError(f"LLM Client initialization failed: {e}")
    
    # ==================== USER STATUS ====================
    
    def get_user_status(self, user: User) -> Dict[str, Any]:
        """Get user's current library status"""
        active_borrows = BorrowTransaction.objects.filter(
            user=user, 
            status__in=['PENDING', 'BORROWED', 'OVERDUE']
        ).count()
        
        fine = getattr(user, 'total_fine', 0)
        remaining_quota = max(0, self.config.MAX_BORROW_PER_USER - active_borrows)
        
        return {
            'active_borrows': active_borrows,
            'fine': fine,
            'can_borrow': active_borrows < self.config.MAX_BORROW_PER_USER and fine == 0,
            'remaining_quota': remaining_quota
        }
    
    def get_user_preferences(self, user: User) -> List[str]:
        """Analyze user's preferences based on borrow history"""
        borrows = BorrowTransaction.objects.filter(
            user=user, 
            status__in=['RETURNED', 'BORROWED', 'PENDING']
        ).select_related('book').values('book__category__name')[:15]
        
        categories = [b['book__category__name'] for b in borrows if b['book__category__name']]
        return list(set(categories))[:3]
    
    # ==================== BOOK VALIDATION ====================
    
    def _is_book_valid(self, book: Book) -> bool:
        """Check if book is valid for recommendation"""
        if not book.title:
            return False
        
        title_lower = book.title.lower()
        for pattern in self.config.INAPPROPRIATE_BOOK_PATTERNS:
            if pattern in title_lower:
                return False
        
        return True
    
    # ==================== DYNAMIC CONTEXT ====================
    
    def get_dynamic_context(self, user: User, user_message: str) -> str:
        """Auto-generate context from database based on user message"""
        query = Book.objects.filter(
            status='AVAILABLE', 
            quantity__gt=0
        ).exclude(borrow_records__user=user)
        
        user_msg_lower = user_message.lower()
        
        # Check for free books search
        is_searching_free = any(
            word in user_msg_lower 
            for word in ["free", "miễn phí"]
        )
        if is_searching_free:
            query = query.filter(Q(price=0) | Q(price__isnull=True))
        
        # Check for category keywords
        keywords = user_msg_lower.split()
        for keyword in keywords:
            try:
                category = Category.objects.filter(name__icontains=keyword).first()
                if category:
                    searched = query.filter(category=category).order_by('title')[:10]
                    if searched.exists():
                        book_list = self._format_book_results(searched)
                        return f"📚 Thư viện có {len(searched)} sách trong mục '{category.name}':\n{book_list}"
            except:
                continue
        
        # Search by keywords
        stop_words = {
            'có', 'sách', 'nào', 'về', 'không', 'tìm', 'cho', 'mình',
            'cuốn', 'thể', 'loại', 'muốn', 'đọc', 'free', 'miễn', 'phí'
        }
        search_terms = [w for w in keywords if w not in stop_words and len(w) > 2]
        
        if search_terms:
            q_objects = Q()
            for term in search_terms:
                q_objects |= (
                    Q(title__icontains=term) | 
                    Q(author__icontains=term) | 
                    Q(category__name__icontains=term)
                )
            
            searched = [b for b in query.filter(q_objects).distinct()[:5] 
                       if self._is_book_valid(b)]
            if searched:
                book_list = self._format_book_results(searched)
                return f"📚 Tìm thấy {len(searched)} cuốn sách phù hợp:\n{book_list}"
        
        # Recommend by preferences
        user_categories = self.get_user_preferences(user)
        if user_categories and not is_searching_free:
            query_pref = query.filter(category__name__in=user_categories)
            if query_pref.exists():
                query = query_pref
        
        query = query.annotate(borrow_count=Count('borrow_records')).order_by('-borrow_count')
        recs = [
            self.book_formatter.format_book_info(b)
            for b in query[:5] if self._is_book_valid(b)
        ][:3]
        
        # Add free books
        if not is_searching_free:
            free_books_all = Book.objects.filter(
                Q(price=0) | Q(price__isnull=True),
                status='AVAILABLE',
                quantity__gt=0
            ).exclude(borrow_records__user=user).order_by('?')[:10]
            
            free_books = [b for b in free_books_all if self._is_book_valid(b)][:2]
            free_recs = [self.book_formatter.format_book_info(b) for b in free_books]
            
            if free_recs:
                return (
                    "Gợi ý sách hay thư viện đang có sẵn:\n" + 
                    "\n".join(recs) + 
                    "\n\nSách MIỄN PHÍ có thể gợi ý thêm:\n" + 
                    "\n".join(free_recs)
                )
        
        result = "\n".join(recs) if recs else "Hiện thư viện đang cập nhật thêm sách mới."
        return "Gợi ý sách hay thư viện đang có sẵn:\n" + result
    
    def _format_book_results(self, books) -> str:
        """Format book search results"""
        return "\n".join([
            f"- '{b.title}' (Tác giả: {b.author or 'N/A'} | "
            f"{('💰 ' + str(b.price) + ' VNĐ') if b.price and b.price > 0 else '✨ Miễn phí'} "
            f"| SL: {b.quantity})"
            for b in books
        ])
    
    # ==================== CHAT MAIN ====================
    
    def chat(
        self,
        user_message: str,
        user: User,
        chat_history: Optional[List[Dict[str, str]]] = None,
        request=None
    ) -> str:
        """
        Main chat method - process user message and return response
        """
        try:
            logger.debug(f"[CHAT] Message from {user.username}: '{user_message}'")
            
            msg_stripped = user_message.strip()
            msg_lower = user_message.lower()
            
            # ===== STEP 1: Check for book selection response =====
            if msg_stripped in ['1', '2', '3']:
                logger.info(f"[CHAT] User selected option: {msg_stripped}")
                result = self._handle_book_selection(user, msg_stripped)
                if result:
                    return result
            
            # ===== STEP 2: Check for pending borrow datetime response =====
            cache_key = f"pending_borrow_{user.id}"
            pending_data = self.cache.get(cache_key)
            
            if pending_data and pending_data.get('waiting_for_datetime'):
                result = self._handle_pending_datetime(user, user_message, pending_data)
                if result:
                    return result
            
            # ===== STEP 3: Check intent with registry =====
            logger.debug(f"[CHAT] Checking intents...")
            intents = self.intent_registry.detect(user_message)
            
            if intents and intents[0].intent_type == 'borrow':
                logger.info(f"[CHAT] Borrow intent detected")
                return self._handle_borrow_intent(user, intents[0])
            
            # ===== STEP 4: Use LLM for general chat =====
            logger.debug(f"[CHAT] Using LLM for general chat")
            return self._call_llm(user, user_message, chat_history)
        
        except Exception as e:
            logger.error(f"[CHAT] Error: {str(e)}", exc_info=True)
            return self.error_handler.handle_error(e, context="chat")
    
    # ==================== INTENT HANDLERS ====================
    
    def _handle_book_selection(self, user: User, selection: str) -> Optional[str]:
        """Handle user selecting a book (1, 2, or 3)"""
        try:
            cache_key = f"pending_borrow_{user.id}"
            cached_data = self.cache.get(cache_key)
            
            if not cached_data:
                return None
            
            books_data = cached_data.get('books', [])
            idx = int(selection) - 1
            
            if idx < 0 or idx >= len(books_data):
                return None
            
            selected = books_data[idx]
            book = Book.objects.get(id=selected['id'])
            
            # Update cache for datetime prompt
            intent = cached_data.get('intent', {})
            self.cache.set(cache_key, {
                'book_id': book.id,
                'book_title': book.title,
                'intent': intent,
                'waiting_for_datetime': True
            }, self.config.CACHE_TIMEOUT_SECONDS)
            
            return self.borrow_formatter.format_ask_datetime(book)
        
        except Exception as e:
            logger.error(f"[BOOK_SELECTION] Error: {str(e)}", exc_info=True)
            return None
    
    def _handle_pending_datetime(self, user: User, message: str, pending_data: Dict) -> Optional[str]:
        """Handle datetime response for borrow"""
        try:
            book_id = pending_data.get('book_id')
            book = Book.objects.get(id=book_id)
            
            # Parse shift
            shift = None
            if 'sáng' in message.lower() or 'morning' in message.lower():
                shift = 'SANG'
            elif 'chiều' in message.lower() or 'afternoon' in message.lower():
                shift = 'CHIEU'
            
            if not shift:
                return "Bạn chưa nêu ca (sáng hoặc chiều). Vui lòng trả lời: sáng hay chiều?"
            
            # Parse date
            pickup_date = self._parse_date_from_message(message)
            if not pickup_date:
                return "Bạn chưa nêu ngày. Vui lòng trả lời (ví dụ: 21/04/2026)."
            
            # Create borrow transaction
            result = self.create_borrow_transaction(user, book, pickup_date, shift)
            
            if result['success']:
                self.cache.delete(f"pending_borrow_{user.id}")
            
            return result['message']
        
        except Exception as e:
            logger.error(f"[PENDING_DATETIME] Error: {str(e)}", exc_info=True)
            return None
    
    def _handle_borrow_intent(self, user: User, intent: IntentResult) -> str:
        """Handle borrow intent"""
        # Check if user can borrow
        user_status = self.get_user_status(user)
        if not user_status['can_borrow']:
            if user_status['fine'] > 0:
                return f"❌ Bạn có nợ {user_status['fine']} VNĐ. Vui lòng thanh toán trước khi mượn tiếp!"
            else:
                return "❌ Bạn đã mượn tối đa 4 cuốn. Vui lòng trả một số sách trước!"
        
        # Get books based on keywords
        keywords = intent.data.get('book_keywords', [])
        books = self._search_books(keywords, exclude_user=user)
        
        if not books:
            return "Hiện tại thư viện chưa có sách phù hợp với yêu cầu của bạn."
        
        # If only one book and have datetime, borrow immediately
        if len(books) == 1:
            book = books[0]
            if intent.data.get('preferred_date') and intent.data.get('preferred_shift'):
                result = self.create_borrow_transaction(
                    user, book,
                    intent.data['preferred_date'],
                    intent.data['preferred_shift']
                )
                return result['message']
            else:
                # Save to cache and ask for datetime
                cache_key = f"pending_borrow_{user.id}"
                self.cache.set(cache_key, {
                    'book_id': book.id,
                    'book_title': book.title,
                    'intent': intent.data,
                    'waiting_for_datetime': True
                }, self.config.CACHE_TIMEOUT_SECONDS)
                return self.borrow_formatter.format_ask_datetime(book)
        
        # Multiple books - ask for selection
        valid_books = [b for b in books[:3] if self._is_book_valid(b)]
        
        cache_key = f"pending_borrow_{user.id}"
        self.cache.set(cache_key, {
            'books': [{'id': b.id, 'title': b.title} for b in valid_books],
            'intent': intent.data,
            'waiting_for_selection': True
        }, self.config.CACHE_TIMEOUT_SECONDS)
        
        return self.borrow_formatter.format_borrow_options(valid_books)
    
    # ==================== UTILITIES ====================
    
    def _search_books(self, keywords: List[str], exclude_user: User = None) -> List[Book]:
        """Search books by keywords"""
        query = Book.objects.filter(status='AVAILABLE', quantity__gt=0)
        
        if exclude_user:
            query = query.exclude(borrow_records__user=exclude_user)
        
        if not keywords:
            return list(query[:5])
        
        q_objects = Q()
        for keyword in keywords:
            q_objects |= (
                Q(title__icontains=keyword) |
                Q(author__icontains=keyword) |
                Q(category__name__icontains=keyword)
            )
        
        return list(query.filter(q_objects).distinct()[:5])
    
    def _parse_date_from_message(self, message: str) -> Optional[str]:
        """Parse date from user message"""
        import re
        
        # Try DD/MM/YYYY
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', message)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month:0>2}-{day:0>2}"
        
        # Try YYYY-MM-DD
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', message)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month:0>2}-{day:0>2}"
        
        # Try keywords
        msg_lower = message.lower()
        for keyword, days_offset in self.config.DATE_KEYWORDS.items():
            if keyword in msg_lower:
                return (timezone.now().date() + timedelta(days=days_offset)).isoformat()
        
        return None
    
    def _call_llm(self, user: User, message: str, history: Optional[List] = None) -> str:
        """Call LLM API"""
        try:
            user_status = self.get_user_status(user)
            dynamic_context = self.get_dynamic_context(user, message)
            
            system_prompt = self._build_system_prompt(user_status, dynamic_context)
            
            # Build messages
            messages = []
            if history:
                for msg in history:
                    messages.append(Message(msg['role'], msg['text']))
            
            messages.append(Message('user', message))
            
            # Generate response
            response = self.llm_client.generate(
                messages,
                system_prompt=system_prompt,
                temperature=self.config.API_TEMPERATURE
            )
            
            logger.debug(f"[LLM] Generated response - length: {len(response)}")
            return response
        
        except Exception as e:
            logger.error(f"[LLM] Error: {str(e)}")
            return self.error_handler.handle_error(e, context="llm_call")
    
    def _build_system_prompt(self, user_status: Dict, dynamic_context: str) -> str:
        """Build system prompt for LLM"""
        return f"""Bạn là Alovu Assistant - Thủ thư AI xuất sắc và thân thiện của Thư viện Alovu.

QUY ĐỊNH THƯ VIỆN:
1. Mượn tối đa: {self.config.MAX_BORROW_PER_USER} cuốn/người
2. Thời hạn mượn: {self.config.BORROW_DURATION_DAYS} ngày/cuốn
3. Phạt trễ: {self.config.LATE_FEE_PER_DAY} VNĐ/ngày, -{self.config.PENALTY_POINTS_PER_DAY} điểm/ngày
4. Mất sách: Đền {self.config.BOOK_REPLACEMENT_PERCENT}% giá trị

HỒ SƠ SINH VIÊN:
- Đang mượn: {user_status['active_borrows']}/{self.config.MAX_BORROW_PER_USER} cuốn
- Có thể mượn thêm: {user_status['remaining_quota']} cuốn
- Tiền nợ: {user_status['fine']} VNĐ
- Quyền mượn: {'ĐƯỢC PHÉP' if user_status['can_borrow'] else 'BỊ CHẶN'}

SỐ LIỆU KHO SÁCH:
{dynamic_context}

NGUYÊN TẮC:
- Trả lời ngắn gọn (2-3 câu)
- Chủ động gợi ý sách miễn phí
- Sử dụng emoji thân thiện
- Xưng hô 'Mình - Bạn'"""
    
    # ==================== BORROW TRANSACTION ====================
    
    def create_borrow_transaction(
        self,
        user: User,
        book: Book,
        pickup_date: str,
        pickup_shift: str
    ) -> Dict[str, Any]:
        """Create borrow transaction"""
        from django.db import transaction as db_transaction
        from datetime import date as date_class
        
        try:
            # Validate date
            try:
                pickup_date_obj = date_class.fromisoformat(pickup_date)
                today = timezone.now().date()
                if pickup_date_obj < today:
                    return {
                        'success': False,
                        'message': f"⚠️ Ngày {pickup_date} đã qua!"
                    }
            except:
                return {
                    'success': False,
                    'message': "❌ Ngày không hợp lệ"
                }
            
            with db_transaction.atomic():
                due_date = timezone.now().date() + timedelta(days=self.config.BORROW_DURATION_DAYS)
                is_premium = book.price and book.price > 0
                
                borrow = BorrowTransaction.objects.create(
                    user=user,
                    book=book,
                    due_date=due_date,
                    status='PENDING',
                    payment_method='CASH' if is_premium else 'FREE',
                    is_paid=not is_premium,
                    pickup_date=pickup_date,
                    pickup_shift=pickup_shift
                )
                
                # Reduce quantity
                book.quantity -= 1
                book.save()
                
                # Create notification
                shift_name = self.config.SHIFTS.get(pickup_shift, pickup_shift)
                price_part = f" Phí: {book.price:,.0f} VNĐ" if is_premium else ""
                message = (
                    f"✓ Đã đăng ký mượn '{book.title}'. "
                    f"Nhận vào {shift_name} ngày {pickup_date}.{price_part}"
                )
                
                Notification.objects.create(
                    user=user,
                    message=message,
                    type='SYSTEM',
                    status='UNREAD'
                )
                
                logger.info(f"[BORROW] Transaction created: {borrow.id}")
                
                return {
                    'success': True,
                    'message': message,
                    'transaction_id': borrow.id
                }
        
        except Exception as e:
            logger.error(f"[BORROW] Error: {str(e)}")
            return {
                'success': False,
                'message': f"Lỗi hệ thống: {str(e)}"
            }
    
    # ==================== CONFIGURATION ====================
    
    def update_config(self, **kwargs):
        """Update configuration dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"[CONFIG] Updated {key} = {value}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self.config.to_dict()
    
    def register_intent_handler(self, handler):
        """Register custom intent handler"""
        self.intent_registry.register(handler)
        logger.info(f"[SERVICE] Registered intent handler: {handler.intent_type}")
