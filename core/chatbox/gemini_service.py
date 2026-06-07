import google.genai as genai
from google.genai import types
from django.conf import settings
from django.db.models import Q, Count
from core.models import Book, User, BorrowTransaction
import time
import logging
from datetime import datetime, timedelta
from .borrow_intent_handler import BorrowIntentHandler
from core.models import Notification
from django.utils import timezone

logger = logging.getLogger(__name__)

# Rate limiting decorator
def rate_limit_gemini(func):
    """Giới hạn 1 request mỗi 5 giây để tránh bị block API"""
    last_call = [0]
    def wrapper(*args, **kwargs):
        elapsed = time.time() - last_call[0]
        if elapsed < 5:
            time.sleep(5 - elapsed)
        result = func(*args, **kwargs)
        last_call[0] = time.time()
        return result
    return wrapper

class GeminiChatService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    def _get_user_status(self, user):
        """Lấy trạng thái thực tế của User"""
        active_borrows = BorrowTransaction.objects.filter(
            user=user, status__in=['PENDING', 'BORROWED', 'OVERDUE']
        ).count()
        fine = getattr(user, 'total_fine', 0)
        return {
            'active_borrows': active_borrows,
            'fine': fine,
            'can_borrow': active_borrows < 4 and fine == 0,
            'remaining_quota': max(0, 4 - active_borrows) # SỐ LƯỢNG SÁCH CÒN ĐƯỢC MƯỢN THÊM
        }

    def get_user_preferences(self, user):
        """Phân tích sở thích dựa trên lịch sử mượn"""
        borrows = BorrowTransaction.objects.filter(
            user=user, 
            status__in=['RETURNED', 'BORROWED', 'PENDING']
        ).select_related('book').values('book__category__name')[:15]
        
        categories = [b['book__category__name'] for b in borrows if b['book__category__name']]
        return list(set(categories))[:3]
    
    def _is_book_valid(self, book):
        """Kiểm tra xem sách có hợp lệ để gợi ý không (lọc sách có tên cục súc)"""
        if not book.title:
            return False
        title_lower = book.title.lower()
        # Lọc những cuốn có tên vô ý nghĩa, cục súc, hoặc spam
        inappropriate_patterns = [
            'con cu', 'lmao', 'haha', 'xxx', '123', 'test', 'spam',
            'bla', 'foo', 'bar', 'aaa', 'bbb', 'ccc', '...'
        ]
        for pattern in inappropriate_patterns:
            if pattern in title_lower:
                return False
        return True

    def get_dynamic_context(self, user, user_message):
        """Tự động rà soát database dựa trên câu chat của người dùng (Bao gồm xử lý sách Free)"""
        from core.models import Category
        
        query = Book.objects.filter(status='AVAILABLE', quantity__gt=0).exclude(borrow_records__user=user)
        user_msg_lower = user_message.lower()

        # 1. Bắt từ khóa tìm sách Miễn phí / Free
        is_searching_free = "free" in user_msg_lower or "miễn phí" in user_msg_lower
        if is_searching_free:
            query = query.filter(Q(price=0) | Q(price__isnull=True))

        # 2. Kiểm tra xem có tìm category nào không
        keywords = user_msg_lower.split()
        for keyword in keywords:
            category_match = Category.objects.filter(name__icontains=keyword).first()
            if category_match:
                searched_books = query.filter(category=category_match).order_by('title')[:10]
                if searched_books.exists():
                    book_list = "\n".join([
                        f"- '{b.title}' (Tác giả: {b.author or 'N/A'} | {('💰 ' + str(b.price) + ' VNĐ') if b.price and b.price > 0 else '✨ Miễn phí'} | SL: {b.quantity})"
                        for b in searched_books
                    ])
                    return f"📚 Thư viện có {len(searched_books)} sách trong mục '{category_match.name}':\n{book_list}"

        # 3. Tìm kiếm đích danh theo từ khóa
        stop_words = {'có', 'sách', 'nào', 'về', 'không', 'tìm', 'cho', 'mình', 'cuốn', 'thể', 'loại', 'muốn', 'đọc', 'free', 'miễn', 'phí', 'trong', 'mục', 'gì', 'nào'}
        search_terms = [w for w in keywords if w not in stop_words and len(w) > 2]
        
        if search_terms:
            q_objects = Q()
            for term in search_terms:
                q_objects |= Q(title__icontains=term) | Q(author__icontains=term) | Q(category__name__icontains=term)
            
            searched_books = [b for b in query.filter(q_objects).distinct()[:5] if self._is_book_valid(b)]
            if searched_books:
                book_list = "\n".join([
                    f"- '{b.title}' (Tác giả: {b.author or 'N/A'} | {('💰 ' + str(b.price) + ' VNĐ') if b.price and b.price > 0 else '✨ Miễn phí'})"
                    for b in searched_books
                ])
                return f"📚 Tìm thấy {len(searched_books)} cuốn sách phù hợp:\n{book_list}"
        
        # 4. Lọc theo sở thích (nếu không chủ động tìm sách free)
        user_categories = self.get_user_preferences(user)
        if user_categories and not is_searching_free:
            query_pref = query.filter(category__name__in=user_categories)
            if query_pref.exists():
                query = query_pref
            
        query = query.annotate(borrow_count=Count('borrow_records')).order_by('-borrow_count')
        recs = [f"- {b.title} (Tác giả: {b.author or 'Đang cập nhật'} | {b.price if b.price and b.price > 0 else 'Miễn phí'})" for b in query[:5] if self._is_book_valid(b)][:3]
        
        # 4. Luôn kẹp thêm 1-2 cuốn sách FREE vào cuối cùng để AI chủ động gợi ý (NẾU CHƯA TÌM)
        if not is_searching_free:
            free_books_all = Book.objects.filter(Q(price=0) | Q(price__isnull=True), status='AVAILABLE', quantity__gt=0).exclude(borrow_records__user=user).order_by('?')[:10]
            free_books = [b for b in free_books_all if self._is_book_valid(b)][:2]
            free_recs = [f"- {b.title} (Tác giả: {b.author or 'Đang cập nhật'} | Miễn phí)" for b in free_books]
            if free_recs:
                 return "Gợi ý sách hay thư viện đang có sẵn:\n" + "\n".join(recs) + "\n\nSách MIỄN PHÍ có thể gợi ý thêm:\n" + "\n".join(free_recs)

        return "Gợi ý sách hay thư viện đang có sẵn:\n" + "\n".join(recs) if recs else "Hiện thư viện đang cập nhật thêm sách mới."

    def chat(self, user_message, user, chat_history=None, request=None):
        """Xử lý chat thông minh với Context-Aware & Memory"""
        try:
            from django.core.cache import cache
            
            msg_stripped = user_message.strip()
            msg_lower = user_message.lower()
            
            logger.debug(f"[CHAT] Processing message from {user.username}: '{user_message}'")
            
            # ===== BƯỚC 0: KIỂM TRA XEM USER CÓ ĐANG CHỌN SÁCH TỪ DANH SÁCH GỢI Ý =====
            if msg_stripped in ['1', '2', '3']:
                logger.info(f"[CHAT] User selected option: {msg_stripped}")
                result = self._handle_book_selection(user, msg_stripped, request)
                if result:
                    return result
            elif msg_stripped.isdigit() and msg_stripped not in ['1', '2', '3']:
                # User chọn số không hợp lệ (không phải 1, 2, 3)
                logger.warning(f"[CHAT] Invalid selection: {msg_stripped}")
                return "❌ Vui lòng chọn 1, 2 hoặc 3. Chọn sai số sẽ không được xử lý!"
            
            # ===== BƯỚC 0B: KIỂM TRA XEM USER CÓ ĐANG TRẢ LỜI NGÀY/GIỜ MƯỢN SÁCH (dùng cache) =====
            cache_key = f"pending_borrow_{user.id}"
            pending_data = cache.get(cache_key)
            
            # CHỈ xử lý pending borrow nếu message có shift/date keywords
            if pending_data and pending_data.get('waiting_for_datetime'):
                import re
                has_shift_or_date = (any(kw in msg_lower for kw in ['sáng', 'chiều', 'morning', 'afternoon']) or
                                   re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{1,2}-\d{1,2}', user_message))
                
                if has_shift_or_date:
                    logger.info(f"[CHAT] Handling pending borrow datetime response: '{user_message}'")
                    result = self._handle_pending_borrow_datetime(user, user_message, pending_data)
                    if result:
                        return result
                else:
                    # Message không có shift/date keywords → xóa pending state & continue
                    logger.debug(f"[CHAT] Message không liên quan đến pending borrow, clearing cache")
                    cache.delete(cache_key)
            
            # ===== BƯỚC 1: KIỂM TRA BORROW INTENT TRƯỚC (không cần Gemini) =====
            logger.debug(f"[CHAT] Checking borrow intent before Gemini...")
            handler = BorrowIntentHandler()
            intent = handler.detect_borrow_intent(user_message)
            
            if intent['has_intent']:
                # Xử lý borrow request ngay lập tức (không phụ thuộc Gemini API)
                logger.info(f"[CHAT] Borrow intent detected in chat() - processing directly")
                can_borrow_result = handler.can_borrow(user)
                
                if not can_borrow_result['can_borrow']:
                    return can_borrow_result['reason']
                
                # ===== STEP 1A: TRY FUZZY MATCH TRƯỚC (Nếu user nhắc cụ thể tên sách) =====
                book_found = None
                if intent.get('book_title_hint'):
                    logger.debug(f"[CHAT] Trying fuzzy match for: '{intent['book_title_hint']}'")
                    book_found = handler.fuzzy_match_title(intent['book_title_hint'], threshold=0.55)
                    
                    if book_found:
                        logger.info(f"[CHAT] Fuzzy match found: {book_found.title}")
                        
                        # Kiểm tra trùng mượn
                        if handler.check_duplicate_borrow(user, book_found):
                            return f"Bạn đang mượn hoặc chờ duyệt cuốn '{book_found.title}' rồi!"
                        
                        # Nếu user đã nêu shift, mượn luôn
                        if intent['preferred_date'] and intent['preferred_shift']:
                            result = self.create_borrow_transaction(user, book_found, intent['preferred_date'], intent['preferred_shift'])
                            return result['message']
                        
                        # Nếu chưa nêu shift, hỏi - LƯU CACHE
                        from django.core.cache import cache
                        cache_key = f"pending_borrow_{user.id}"
                        cache.set(cache_key, {
                            'selected_book_id': book_found.id,
                            'book_id': book_found.id,
                            'book_title': book_found.title,
                            'intent': intent,
                            'waiting_for_datetime': True
                        }, timeout=1800)
                        
                        shift_text = "sáng" if intent['preferred_shift'] == 'SANG' else "chiều" if intent['preferred_shift'] == 'CHIEU' else "khi nào"
                        date_text = intent['preferred_date'] or "khi nào"
                        return f"Tôi sẽ giúp bạn mượn cuốn '{book_found.title}'. Bạn muốn nhận vào ca {shift_text} ngày {date_text}?"
                
                # ===== STEP 1B: KEYWORD SEARCH (Nếu không có hint hoặc fuzzy match không thành công) =====
                books = list(handler.search_books(intent['book_keywords'], exclude_user=user))
                if not books:
                    return "Hiện tại thư viện chưa có sách phù hợp với yêu cầu của bạn. Vui lòng quay lại sau!"
                
                # Nếu có 1 cuốn và đủ info, mượn luôn
                if len(books) == 1 and intent['preferred_date'] and intent['preferred_shift']:
                    book = books[0]
                    if handler.check_duplicate_borrow(user, book):
                        return f"Bạn đang mượn hoặc chờ duyệt cuốn '{book.title}' rồi!"
                    result = self.create_borrow_transaction(user, book, intent['preferred_date'], intent['preferred_shift'])
                    return result['message']
                
                # Nếu nhiều sách, gợi ý - LƯU INTENT VÀO CACHE
                if len(books) > 1:
                    from django.core.cache import cache
                    cache_key = f"pending_borrow_{user.id}"
                    
                    # Lưu danh sách sách + intent (ngày/giờ) vào cache
                    # Chỉ lưu tối đa 3 cuốn và lọc sách không hợp lệ
                    valid_books = [b for b in books[:5] if self._is_book_valid(b)][:3]
                    books_data = [
                        {
                            'id': book.id,
                            'title': book.title,
                            'author': book.author or 'Tác giả không rõ',
                            'price': float(book.price) if book.price else 0
                        }
                        for book in valid_books
                    ]
                    cache.set(cache_key, {
                        'books': books_data,
                        'intent': intent,  # ← QUAN TRỌNG: Lưu intent để khi user chọn có ngày/giờ rồi
                        'waiting_for_selection': True
                    }, timeout=1800)
                    
                    book_list = "\n".join([f"{i+1}. {handler.format_book_info(b)}" for i, b in enumerate(valid_books)])
                    return f"Tôi tìm thấy vài cuốn sách phù hợp:\n{book_list}\n\nBạn muốn mượn cuốn nào? (Trả lời: 1, 2 hoặc 3)"
                
                # 1 cuốn nhưng thiếu ngày/giờ
                book = books[0]
                
                # Lưu cache để xử lý khi user trả lời ngày/giờ
                from django.core.cache import cache
                cache_key = f"pending_borrow_{user.id}"
                cache.set(cache_key, {
                    'books': [{'id': book.id, 'title': book.title, 'author': book.author or 'Tác giả không rõ', 'price': float(book.price) if book.price else 0}],
                    'selected_book_id': book.id,
                    'book_id': book.id,
                    'book_title': book.title,
                    'intent': intent,
                    'waiting_for_datetime': True
                }, timeout=1800)
                
                shift_text = f"ca {('sáng' if intent['preferred_shift'] == 'SANG' else 'chiều')} " if intent['preferred_shift'] else ""
                date_text = f"ngày {intent['preferred_date']}" if intent['preferred_date'] else "khi nào"
                return f"Tôi sẽ giúp bạn mượn cuốn {handler.format_book_info(book)}. Bạn muốn nhận {shift_text}{date_text}?"
            
            # ===== BƯỚC 2: NẾU KHÔNG PHẢI BORROW REQUEST, GỌI GEMINI =====
            logger.debug(f"[CHAT] No borrow intent - using Gemini API")
            user_status = self._get_user_status(user)
            dynamic_books_info = self.get_dynamic_context(user, user_message)
            
            system_instruction = f"""Bạn là Alovu Assistant - Thủ thư AI xuất sắc và thân thiện của Thư viện Alovu.
            
QUY ĐỊNH THƯ VIỆN CHUẨN (TUYỆT ĐỐI TUÂN THỦ):
1. Mượn tối đa: 4 cuốn/người.
2. Thời hạn mượn: 14 ngày/cuốn.
3. Quy định trả trễ: Nếu sinh viên trả sách trễ hạn so với quy định 14 ngày, sẽ bị phạt tiền (5.000 VNĐ/ngày trễ) và bị trừ 5 điểm tích lũy.
4. Quy định mất sách/hỏng sách: Nếu sinh viên làm mất sách hoặc làm hỏng nặng không thể phục hồi, bắt buộc phải đền bù 100% số tiền gốc mua cuốn sách đó.
5. Quy trình mượn: Bấm 'MƯỢN SÁCH' (Sách có phí cần thanh toán tiền mặt/QR) -> Chờ Thủ thư duyệt.

HỒ SƠ CỦA SINH VIÊN ĐANG CHAT (BÁM SÁT THÔNG TIN NÀY):
- Số sách đang mượn/chờ duyệt: {user_status['active_borrows']}/4 cuốn.
- SỐ SÁCH CÒN CÓ THỂ MƯỢN THÊM LÀ: {user_status['remaining_quota']} cuốn.
- Tiền nợ phạt hiện tại: {user_status['fine']} VNĐ.
- Quyền mượn tiếp: {'ĐƯỢC PHÉP' if user_status['can_borrow'] else 'BỊ CHẶN (Phải trả sách hoặc đóng phạt trước khi mượn tiếp)'}.

DỮ LIỆU SÁCH TRONG KHO (Dùng để trả lời câu hỏi hiện tại):
{dynamic_books_info}

NGUYÊN TẮC GIAO TIẾP:
- TRẢ LỜI NGẮN GỌN (tối đa 3-4 câu). Trả lời thẳng vào câu hỏi của sinh viên.
- Chủ động giới thiệu các đầu sách "Miễn phí" nếu thấy phù hợp với ngữ cảnh.
- Nếu sinh viên hỏi "tôi có thể mượn bao nhiêu cuốn nữa", hãy trả lời chính xác là {user_status['remaining_quota']} cuốn dựa trên thông tin hồ sơ của họ.
- Nếu sinh viên hỏi về đền bù, trả trễ, hỏng sách: Cung cấp thông tin phạt trễ hoặc đền 100% giá trị sách như quy định thư viện.
- NẾU SINH VIÊN BỊ CHẶN QUYỀN MƯỢN: Lịch sự từ chối yêu cầu mượn và nhắc nhở số tiền nợ hoặc số sách cần trả.
- Xưng hô 'Mình - Bạn', dùng emoji thân thiện (📚, 💡, ⚠️, ✨).
"""
            # Nạp Lịch sử trò chuyện để Bot có trí nhớ
            contents = []
            if chat_history:
                for msg in chat_history:
                    # Đã sửa lỗi Part.from_text
                    contents.append(types.Content(role=msg['role'], parts=[types.Part.from_text(text=msg['text'])]))
            
            # Nạp câu hỏi mới nhất
            # Đã sửa lỗi Part.from_text
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
            
            # Gọi Gemini với rate limiting
            return self._call_gemini_api(contents, system_instruction)
            
        except Exception as e:
            logger.error(f"Chat Error: {str(e)}", exc_info=True)
            return self._get_mock_response(user_message, user)
    
    @rate_limit_gemini
    def _call_gemini_api(self, contents, system_instruction):
        """Gọi Gemini API với rate limiting"""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                )
            )
            logger.debug(f"[GEMINI API] Success - Response length: {len(response.text)}")
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}")
            raise  # Re-raise để caller xử lý
            
    def _get_mock_response(self, user_message, user):
        """Hệ thống Trả lời Offline khi API lỗi hoặc hết hạn mức"""
        user_msg_lower = user_message.lower()
        user_status = self._get_user_status(user)
        remaining = user_status['remaining_quota']
        
        # Bắt từ khóa hỏi sách Free lúc Offline
        if any(word in user_msg_lower for word in ["free", "miễn phí"]):
            return "💡 Thư viện Alovu có rất nhiều sách Miễn phí (Free) nha! Bạn có thể vào mục 'Kho sách', chọn bộ lọc 'Sách Miễn phí' để xem toàn bộ nhé."

        if any(word in user_msg_lower for word in ["mượn thêm", "bao nhiêu cuốn"]):
            return f"📚 Theo hệ thống, bạn đang giữ {user_status['active_borrows']} cuốn. Bạn có thể mượn thêm tối đa {remaining} cuốn nữa nhé!"

        if any(word in user_msg_lower for word in ["mất sách", "đền", "bị mất", "làm mất"]):
            return "⚠️ Chào bạn, theo quy định nếu làm mất sách hoặc hỏng nặng, bạn sẽ phải đền 100% giá trị tiền gốc của cuốn sách đó. Bạn hãy ra quầy báo ngay cho Thủ thư để được hỗ trợ giải quyết nhé."

        if any(word in user_msg_lower for word in ["trễ", "muộn", "phạt"]):
            return "⚠️ Nếu trả sách trễ hạn 14 ngày, bạn sẽ bị phạt 5.000 VNĐ cho mỗi ngày trễ và bị trừ 5 điểm tích lũy. Nhớ trả sách đúng hạn để không bị khóa quyền mượn sách mới nha!"

        if any(word in user_msg_lower for word in ["mượn", "cách mượn"]):
            if not user_status['can_borrow']:
                return f"⚠️ Mình kiểm tra thấy bạn đang mượn {user_status['active_borrows']}/4 cuốn và nợ {user_status['fine']} VNĐ tiền phạt. Bạn cần hoàn tất các khoản này trước khi mượn thêm nhé!"
            return "📚 Rất dễ! Tìm sách ưng ý -> Bấm 'MƯỢN SÁCH' -> Xác nhận thanh toán (nếu có phí) -> Chờ Thủ thư duyệt."
            
        if any(word in user_msg_lower for word in ["gợi ý", "sách hay"]):
            return "💡 Bạn thử dạo một vòng trang chủ xem sao, hệ thống đang cập nhật rất nhiều đầu sách miễn phí và sách VIP mới đó! ✨"
        if any(word in user_msg_lower for word in ["quốc việt", "việt"]):
            return "💡 lịt pẹ việt nha ✨"
            
        return "👋 Chào bạn! Trợ lý AI Alovu đây. Hệ thống đang hơi quá tải một chút do quá nhiều bạn sinh viên đang sử dụng, nhưng mình vẫn có thể giải đáp các quy định cơ bản. Bạn cần giúp gì nào? 😊"

    def _save_pending_books_to_session(self, user, books, intent):
        """Lưu danh sách sách vào database tạm thời để xử lý khi user chọn"""
        try:
            from django.core.cache import cache
            # Lưu vào cache với key theo user_id (hết hạn sau 30 phút)
            cache_key = f"pending_borrow_{user.id}"
            books_data = [
                {
                    'id': book.id,
                    'title': book.title,
                    'author': book.author or 'Tác giả không rõ',
                    'price': float(book.price) if book.price else 0
                }
                for book in books
            ]
            cache.set(cache_key, {
                'books': books_data,
                'intent': intent  # Lưu intent gốc để dùng lại
            }, timeout=1800)  # 30 phút
            logger.debug(f"[CACHE] Saved {len(books)} books for user {user.id} - cache key: {cache_key}")
        except Exception as e:
            logger.warning(f"[CACHE] Failed to save pending books: {str(e)}")
    
    def _handle_shift_and_date_response(self, user, msg_lower):
        """
        Xử lý khi user trả lời shift (sáng/chiều) sau khi bot hỏi
        Returns: Response string hoặc None nếu không phải shift response
        """
        try:
            from django.core.cache import cache
            cache_key = f"pending_borrow_{user.id}"  # ← FIX: Dùng key thống nhất
            cached_data = cache.get(cache_key)
            
            if not cached_data or 'selected_book_id' not in cached_data:
                # Không có pending book, ignore
                return None
            
            # Kiểm tra xem message có phải shift keyword
            shift_code = None
            for shift_keyword in ['sáng', 'chiều', 'morning', 'afternoon']:
                if shift_keyword in msg_lower:
                    shift_code = 'SANG' if shift_keyword in ['sáng', 'morning'] else 'CHIEU'
                    break
            
            if not shift_code:
                # Không phải shift response, ignore
                return None
            
            # Lấy book từ cache
            book_id = cached_data['selected_book_id']
            from core.models import Book
            try:
                book = Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                cache.delete(cache_key)
                logger.error(f"[SHIFT RESPONSE] Book {book_id} not found")
                return None
            
            # Mặc định là hôm nay nếu user không nói ngày
            pickup_date = timezone.now().date().isoformat()
            
            # Cố gắng tìm ngày trong message
            handler = BorrowIntentHandler()
            for date_keyword, days_offset in handler.DATE_KEYWORDS.items():
                if date_keyword in msg_lower:
                    pickup_date = (timezone.now().date() + timedelta(days=days_offset)).isoformat()
                    break
            
            logger.info(f"[SHIFT RESPONSE] Extracted shift={shift_code}, date={pickup_date}")
            
            # Mượn sách
            result = self.create_borrow_transaction(user, book, pickup_date, shift_code)
            
            # Xóa cache sau khi thành công
            cache.delete(cache_key)
            return result['message']
            
        except Exception as e:
            logger.error(f"[SHIFT RESPONSE] Error: {str(e)}", exc_info=True)
            return None
    
    def _handle_book_selection(self, user, selection, request=None):
        """Xử lý khi user chọn cuốn sách từ danh sách (trả lời 1, 2 hoặc 3)"""
        try:
            from django.core.cache import cache
            cache_key = f"pending_borrow_{user.id}"  # ← FIX: Dùng key thống nhất
            cached_data = cache.get(cache_key)
            
            if not cached_data:
                logger.warning(f"[SELECTION] No pending books for user {user.id}")
                return None
            
            books_data = cached_data['books']
            intent = cached_data.get('intent', {})
            
            # Lấy index (1-based to 0-based)
            try:
                idx = int(selection) - 1
            except ValueError:
                # Không phải số, return None để xử lý bình thường
                return None
            
            if idx < 0 or idx >= len(books_data):
                return None
            
            selected_book_data = books_data[idx]
            
            # Lấy book object từ DB
            from core.models import Book
            try:
                book = Book.objects.get(id=selected_book_data['id'])
            except Book.DoesNotExist:
                logger.error(f"[SELECTION] Book {selected_book_data['id']} not found")
                return None
            
            # Kiểm tra điều kiện mượn lần nữa
            handler = BorrowIntentHandler()
            can_borrow_result = handler.can_borrow(user)
            if not can_borrow_result['can_borrow']:
                cache.delete(cache_key)
                return can_borrow_result['reason']
            
            # Kiểm tra trùng mượn
            if handler.check_duplicate_borrow(user, book):
                cache.delete(cache_key)
                return f"Bạn đang mượn hoặc chờ duyệt cuốn '{book.title}' rồi!"
            
            # Cần ngày/ca để mượn
            if not intent.get('preferred_date') or not intent.get('preferred_shift'):
                # Lưu lại selection để lần sau biết đang chọn cuốn nào
                from django.core.cache import cache
                cache_key = f"pending_borrow_{user.id}"
                cache.set(cache_key, {
                    'books': books_data,
                    'intent': intent,
                    'selected_book_id': book.id,
                    'book_id': book.id,
                    'book_title': book.title,
                    'waiting_for_datetime': True
                }, timeout=1800)
                
                shift_text = "sáng hay chiều"
                return f"✅ Tôi sẽ giúp bạn mượn '{book.title}'. Bạn muốn nhận vào buổi {shift_text} ngày nào?\n\n💡 Ví dụ: sáng ngày 21/04/2026 hoặc ca chiều 21/04/2026"
            
            # Mượn luôn
            result = self.create_borrow_transaction(user, book, intent['preferred_date'], intent['preferred_shift'])
            
            # Xóa cache sau khi thành công
            cache.delete(cache_key)
            return result['message']
            
        except Exception as e:
            logger.error(f"[SELECTION] Error handling book selection: {str(e)}", exc_info=True)
            return None
    
    def _handle_pending_borrow_datetime(self, user, user_message, pending_data):
        """
        Xử lý khi user trả lời ngày/giờ mượn sách sau khi chọn cuốn sách
        """
        try:
            from django.core.cache import cache
            from core.models import Book
            import re
            
            book_id = pending_data.get('book_id')
            book_title = pending_data.get('book_title')
            
            logger.info(f"[DATETIME RESPONSE] Processing for {book_title}: '{user_message}'")
            
            # Lấy book
            try:
                book = Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                logger.error(f"[DATETIME RESPONSE] Book {book_id} not found")
                cache.delete(f"pending_borrow_{user.id}")
                return None
            
            msg_lower = user_message.lower()
            
            # ===== Parse SHIFT =====
            shift_code = None
            if 'sáng' in msg_lower or 'morning' in msg_lower:
                shift_code = 'SANG'
            elif 'chiều' in msg_lower or 'afternoon' in msg_lower:
                shift_code = 'CHIEU'
            
            if not shift_code:
                logger.debug(f"[DATETIME RESPONSE] No shift (sáng/chiều) found")
                # Hỏi lại
                return "Bạn chưa nêu ca (sáng hoặc chiều). Vui lòng trả lời: sáng hay chiều?"
            
            # ===== Parse DATE =====
            pickup_date = None
            
            # Pattern: DD/MM/YYYY (ưu tiên)
            date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', user_message)
            if date_match:
                day, month, year = date_match.groups()
                pickup_date = f"{year}-{month:0>2}-{day:0>2}"
                logger.debug(f"[DATETIME RESPONSE] Matched DD/MM/YYYY: {pickup_date}")
            
            # Pattern: YYYY-MM-DD
            if not pickup_date:
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', user_message)
                if date_match:
                    year, month, day = date_match.groups()
                    pickup_date = f"{year}-{month:0>2}-{day:0>2}"
                    logger.debug(f"[DATETIME RESPONSE] Matched YYYY-MM-DD: {pickup_date}")
            
            # Try keywords (hôm nay, ngày mai, etc.)
            if not pickup_date:
                handler = BorrowIntentHandler()
                for date_keyword, days_offset in handler.DATE_KEYWORDS.items():
                    if date_keyword in msg_lower:
                        pickup_date = (timezone.now().date() + timedelta(days=days_offset)).isoformat()
                        logger.debug(f"[DATETIME RESPONSE] Matched keyword '{date_keyword}': {pickup_date}")
                        break
            
            if not pickup_date:
                logger.debug(f"[DATETIME RESPONSE] No date found - asking for clarification")
                return "Bạn chưa nêu ngày (ví dụ: 21/04/2026 hoặc ngày mai). Vui lòng trả lời: ngày nào?"
            
            # ===== KIỂM TRA NGÀY KHÔNG ĐƯỢC TRONG QUÁ KHỨ =====
            from datetime import date as date_class
            try:
                pickup_date_obj = date_class.fromisoformat(pickup_date)
                today = timezone.now().date()
                
                if pickup_date_obj < today:
                    logger.warning(f"[DATETIME RESPONSE] Invalid date (in the past): {pickup_date} vs today {today}")
                    return f"⚠️ Ngày {pickup_date} đã qua rồi! Bạn phải chọn ngày từ hôm nay ({today.strftime('%d/%m/%Y')}) trở đi. Vui lòng chọn lại."
            except Exception as e:
                logger.error(f"[DATETIME RESPONSE] Error parsing date: {str(e)}")
                return "❌ Ngày không hợp lệ. Vui lòng chọn lại (ví dụ: 23/04/2026 hoặc ngày mai)."
            
            logger.info(f"[DATETIME RESPONSE] Successfully parsed - Shift: {shift_code}, Date: {pickup_date}")
            
            # Tạo giao dịch mượn
            result = self.create_borrow_transaction(user, book, pickup_date, shift_code)
            
            # Xóa pending state
            cache.delete(f"pending_borrow_{user.id}")
            
            return result['message']
        
        except Exception as e:
            logger.error(f"[DATETIME RESPONSE] Error: {str(e)}", exc_info=True)
            return None

    def create_borrow_transaction(self, user, book, pickup_date, pickup_shift):
        """
        Tạo giao dịch mượn sách từ AI chatbot
        """
        from core.models import BorrowTransaction
        from django.db import transaction as db_transaction
        from datetime import date as date_class
    
        try:
            # ===== VALIDATE NGÀY =====
            try:
                pickup_date_obj = date_class.fromisoformat(pickup_date)
                today = timezone.now().date()
                if pickup_date_obj < today:
                    return {
                        'success': False,
                        'message': f"⚠️ Ngày {pickup_date} đã qua rồi! Bạn phải chọn ngày từ hôm nay ({today.strftime('%d/%m/%Y')}) trở đi."
                    }
            except Exception as e:
                logger.error(f"[CREATE TRANSACTION] Invalid pickup date: {str(e)}")
                return {
                    'success': False,
                    'message': "❌ Ngày không hợp lệ. Vui lòng kiểm tra lại."
                }
            
            with db_transaction.atomic():
                due_date = timezone.now().date() + timedelta(days=14)
                is_premium = book.price and book.price > 0
            
                borrow_trans = BorrowTransaction.objects.create(
                    user=user,
                    book=book,
                    due_date=due_date,
                    status='PENDING',
                    payment_method='CASH' if is_premium else 'FREE',
                    is_paid=not is_premium,
                    pickup_date=pickup_date,
                    pickup_shift=pickup_shift
                )
                
                # Giảm số lượng sách
                book.quantity -= 1
                book.save()
                
                # Tạo thông báo
                shift_display = "Sáng (07:30-11:30)" if pickup_shift == 'SANG' else "Chiều (13:00-17:00)"
                price_display = f" Phí: {book.price:,.0f} VNĐ" if is_premium else ""
                msg = f"✓ Đã đăng ký mượn '{book.title}'. Nhận vào {shift_display} ngày {pickup_date}.{price_display}"
                
                Notification.objects.create(
                    user=user,
                    message=msg,
                    type='SYSTEM',
                    status='UNREAD'
                )
                
                logger.info(f"[CREATE TRANSACTION] Borrow transaction created - ID: {borrow_trans.id}, User: {user.username}, Book: {book.title}")
                
                return {
                    'success': True,
                    'message': msg,
                    'transaction_id': borrow_trans.id
                }
        except Exception as e:
            logger.error(f"[CREATE TRANSACTION] Error creating borrow transaction: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f"Lỗi hệ thống: {str(e)}"
            }