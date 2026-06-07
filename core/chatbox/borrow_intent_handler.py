# core/chatbox/borrow_intent_handler.py
import re
import logging
from difflib import SequenceMatcher
from django.db.models import Q
from core.models import Book, BorrowTransaction
from datetime import datetime, timedelta
from django.utils import timezone

try:
    from Levenshtein import ratio as levenshtein_ratio
    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False
    levenshtein_ratio = None

logger = logging.getLogger(__name__)

class BorrowIntentHandler:
    """
    Xử lý ý định mượn sách từ tin nhắn của user
    - Nhận diện ý định "muốn mượn sách"
    - Tìm kiếm sách phù hợp
    - Kiểm tra điều kiện mượn
    """
    
    BORROW_KEYWORDS = [
        'mượn', 'muốn đọc', 'muốn đọc', 'có cuốn nào', 'tìm sách', 'giúp mình',
        'cho mình', 'mình mượn', 'mình muốn', 'borrow', 'lend', 'read', 'want',
        'sách nào', 'cuốn nào', 'mượn sách', 'cho mượn', 'vay sách'
    ]
    
    DATE_KEYWORDS = {
        'hôm nay': 0,
        'ngày mai': 1,
        'ngày kia': 2,
        'tuần sau': 7,
        'today': 0,
        'tomorrow': 1,
    }
    
    SHIFT_KEYWORDS = {
        'sáng': 'SANG',
        'chiều': 'CHIEU',
        'morning': 'SANG',
        'afternoon': 'CHIEU',
    }
    
    def detect_borrow_intent(self, message):
        """
        Kiểm tra xem user có ý định mượn sách không
        Returns: {
            'has_intent': bool,
            'book_keywords': list,
            'book_title_hint': str (tên sách user muốn mượn nếu có),
            'preferred_date': date or None,
            'preferred_shift': str or None
        }
        """
        msg_lower = message.lower()
        has_intent = any(keyword in msg_lower for keyword in self.BORROW_KEYWORDS)
        
        logger.debug(f"[BORROW INTENT] Message: '{message}' | Has Intent: {has_intent}")
        
        result = {
            'has_intent': has_intent,
            'book_keywords': [],
            'book_title_hint': None,
            'preferred_date': None,
            'preferred_shift': None
        }
        
        if not has_intent:
            logger.debug(f"[BORROW INTENT] No borrow intent detected")
            return result
        
        # ===== BƯỚC 1: Extract DATE & SHIFT TRƯỚC (để xóa khỏi message) =====
        import re
        msg_for_title = message  # Copy để xóa date/shift
        
        # Extract date patterns
        date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})|(\d{4})-(\d{1,2})-(\d{1,2})', msg_for_title)
        if date_match:
            matched_date = date_match.group(0)
            day, month, year = None, None, None
            
            if '/' in matched_date:
                day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
            else:
                year, month, day = date_match.group(4), date_match.group(5), date_match.group(6)
            
            result['preferred_date'] = f"{year}-{month:0>2}-{day:0>2}"
            msg_for_title = msg_for_title.replace(matched_date, '')  # Xóa date khỏi message
            logger.debug(f"[BORROW INTENT] Extracted date: {result['preferred_date']}")
        
        # Extract shift & date keywords
        for date_keyword, days_offset in self.DATE_KEYWORDS.items():
            if date_keyword in msg_lower:
                if not result['preferred_date']:  # Nếu chưa có date từ regex
                    result['preferred_date'] = (timezone.now().date() + timedelta(days=days_offset)).isoformat()
                msg_for_title = msg_for_title.lower().replace(date_keyword, '')  # Xóa keyword
                break
        
        for shift_keyword, shift_code in self.SHIFT_KEYWORDS.items():
            if shift_keyword in msg_lower:
                result['preferred_shift'] = shift_code
                msg_for_title = msg_for_title.lower().replace(shift_keyword, '')  # Xóa shift keyword
                break
        
        # ===== BƯỚC 2: Extract BOOK TITLE HINT từ phần còn lại =====
        stop_words = {'có', 'sách', 'nào', 'về', 'không', 'tìm', 'cho', 'mình', 'cuốn', 
                      'thể', 'loại', 'muốn', 'đọc', 'mượn', 'giúp', 'borrow', 'about', 'và', 'là', 'cái', 'từ',
                      'hãy', 'vui', 'lòng', 'tôi', 'bạn', 'đó', 'này', 'ngày', 'sáng', 'chiều'}
        
        # Lấy phần sau từ khóa mượn
        words = msg_for_title.split()
        borrow_idx = -1
        for i, w in enumerate(words):
            if any(kw in w for kw in self.BORROW_KEYWORDS):
                borrow_idx = i
                break
        
        # Nếu có từ khóa mượn, phần sau đó là tên sách
        if borrow_idx >= 0:
            book_title_hint = ' '.join(words[borrow_idx + 1:]).strip()
            if book_title_hint:
                result['book_title_hint'] = book_title_hint
                logger.debug(f"[BORROW INTENT] Book title hint: '{book_title_hint}'")
        
        # Trích xuất keywords thông thường
        keywords = [w for w in words if len(w) > 2 and w not in stop_words and not any(kw in w for kw in self.BORROW_KEYWORDS)]
        result['book_keywords'] = keywords[:3]
        
        logger.debug(f"[BORROW INTENT] Keywords: {result['book_keywords']} | Date: {result['preferred_date']} | Shift: {result['preferred_shift']} | Title hint: {result['book_title_hint']}")
        return result
    
    def search_books(self, keywords, exclude_user=None):
        """
        Tìm kiếm sách dựa trên keywords
        Support: category search, title search, author search
        Returns: List[Book] - tối đa 5-10 cuốn phù hợp nhất
        """
        from core.models import Category
        
        if not keywords:
            # Nếu không có keywords, gợi ý sách nổi tiếng
            results = Book.objects.filter(
                status='AVAILABLE',
                quantity__gt=0
            ).order_by('-quantity')[:3]
            logger.debug(f"[SEARCH BOOKS] No keywords - fetching popular books: {[b.title for b in results]}")
            return results
        
        query = Book.objects.filter(status='AVAILABLE', quantity__gt=0)
        
        if exclude_user:
            query = query.exclude(borrow_records__user=exclude_user, 
                                 borrow_records__status__in=['PENDING', 'BORROWED', 'OVERDUE'])
        
        # ===== BƯỚC 1: Kiểm tra xem có category match không =====
        for keyword in keywords:
            category_match = Category.objects.filter(name__icontains=keyword).first()
            if category_match:
                results = query.filter(category=category_match).order_by('title')[:10]
                if results.exists():
                    logger.debug(f"[SEARCH BOOKS] Found category '{category_match.name}': {len(results)} books - {[b.title for b in results]}")
                    return list(results)
        
        # ===== BƯỚC 2: Exact keyword match trên title/author/category =====
        q_objects = Q()
        for keyword in keywords:
            q_objects |= Q(title__icontains=keyword) | Q(author__icontains=keyword) | Q(category__name__icontains=keyword)
        
        results = query.filter(q_objects).distinct()[:5]
        if results.exists():
            logger.debug(f"[SEARCH BOOKS] Keywords: {keywords} | Found: {len(results)} exact matches - {[b.title for b in results]}")
            return list(results)
        
        # ===== BƯỚC 3: Nếu không có exact match, try fuzzy match cho từng keyword =====
        logger.debug(f"[SEARCH BOOKS] No exact match for keywords {keywords} - trying fuzzy match...")
        all_available = list(query)
        fuzzy_results = {}
        
        for keyword in keywords:
            if len(keyword) < 2:
                continue
            fuzzy_book = self.fuzzy_match_title(keyword, threshold=0.5)  # Lower threshold for keyword
            if fuzzy_book:
                score = fuzzy_results.get(fuzzy_book.id, 0)
                fuzzy_results[fuzzy_book.id] = score + 1
        
        # Sort by fuzzy match count
        if fuzzy_results:
            sorted_books = sorted(
                [all_available[i] for i in range(len(all_available)) if all_available[i].id in fuzzy_results],
                key=lambda b: fuzzy_results[b.id],
                reverse=True
            )[:3]
            logger.debug(f"[SEARCH BOOKS] Found {len(sorted_books)} fuzzy matches - {[b.title for b in sorted_books]}")
            return sorted_books
        
        logger.debug(f"[SEARCH BOOKS] No fuzzy match either - returning empty")
        return []
    
    def fuzzy_match_title(self, search_text, threshold=0.6):
        """
        Tìm sách bằng fuzzy matching trên tên
        Support: typos, partial words, word order
        Returns: Book object hoặc None nếu không tìm được
        """
        available_books = Book.objects.filter(
            status='AVAILABLE',
            quantity__gt=0
        )
        
        search_lower = search_text.lower().strip()
        search_words = search_lower.split()
        
        best_match = None
        best_score = 0
        
        for book in available_books:
            book_title_lower = book.title.lower()
            book_words = book_title_lower.split()
            
            # === STRATEGY 1: Full title similarity ===
            if HAS_LEVENSHTEIN and levenshtein_ratio:
                full_similarity = levenshtein_ratio(search_lower, book_title_lower)
            else:
                full_similarity = SequenceMatcher(None, search_lower, book_title_lower).ratio()
            
            # === STRATEGY 2: Word-by-word matching ===
            # Tìm xem search words có match với book words không
            word_scores = []
            for search_word in search_words:
                if len(search_word) < 2:
                    continue
                best_word_score = 0
                for book_word in book_words:
                    if HAS_LEVENSHTEIN and levenshtein_ratio:
                        word_similarity = levenshtein_ratio(search_word, book_word)
                    else:
                        word_similarity = SequenceMatcher(None, search_word, book_word).ratio()
                    best_word_score = max(best_word_score, word_similarity)
                if best_word_score > 0:
                    word_scores.append(best_word_score)
            
            # Average word similarity
            word_similarity = sum(word_scores) / len(word_scores) if word_scores else 0
            
            # === STRATEGY 3: Substring match ===
            substring_match = 1.0 if search_lower in book_title_lower or book_title_lower in search_lower else 0
            
            # === COMBINE scores ===
            # Priority: exact substring > word-by-word > full title
            combined_score = max(
                substring_match * 0.95,           # Exact substring match
                word_similarity * 0.8,             # Word matching
                full_similarity * 0.5               # Full sequence match
            )
            
            logger.debug(f"[FUZZY MATCH] '{search_text}' vs '{book.title}': full={full_similarity:.2f}, words={word_similarity:.2f}, substring={substring_match:.2f}, combined={combined_score:.2f}")
            
            if combined_score > best_score:
                best_score = combined_score
                best_match = book
        
        if best_score >= threshold:
            logger.info(f"[FUZZY MATCH] Found match: '{best_match.title}' (score: {best_score:.2f})")
            return best_match
        
        logger.debug(f"[FUZZY MATCH] No match found (best score: {best_score:.2f})")
        return None
    
    def can_borrow(self, user):
        """
        Kiểm tra user có thể mượn sách không
        Returns: {
            'can_borrow': bool,
            'reason': str,
            'active_count': int,
            'remaining_quota': int
        }
        """
        # 1. Kiểm tra phí phạt
        if user.total_fine > 0:
            return {
                'can_borrow': False,
                'reason': f"Bạn đang nợ {user.total_fine:,.0f} VNĐ phí phạt. Vui lòng thanh toán trước!",
                'active_count': 0,
                'remaining_quota': 0
            }
        
        # 2. Kiểm tra hồ sơ
        if not getattr(user, 'msv', None) or not getattr(user, 'lop', None):
            return {
                'can_borrow': False,
                'reason': "Bạn chưa cập nhật MSSV và Lớp trong hồ sơ. Vui lòng cập nhật trước!",
                'active_count': 0,
                'remaining_quota': 0
            }
        
        # 3. Kiểm tra số lượng sách đang mượn
        active_count = BorrowTransaction.objects.filter(
            user=user,
            status__in=['PENDING', 'BORROWED', 'OVERDUE']
        ).count()
        
        if active_count >= 4:
            return {
                'can_borrow': False,
                'reason': f"Bạn đang mượn {active_count} cuốn rồi. Tối đa chỉ được 4 cuốn!",
                'active_count': active_count,
                'remaining_quota': 0
            }
        
        return {
            'can_borrow': True,
            'reason': "OK",
            'active_count': active_count,
            'remaining_quota': 4 - active_count
        }
    
    def check_duplicate_borrow(self, user, book):
        """
        Kiểm tra user đã mượn cuốn sách này chưa
        """
        return BorrowTransaction.objects.filter(
            user=user,
            book=book,
            status__in=['PENDING', 'BORROWED', 'OVERDUE']
        ).exists()
    
    def format_book_info(self, book):
        """Format thông tin sách cho phản hồi AI"""
        price_display = f"{book.price:,.0f} VNĐ" if book.price and book.price > 0 else "Miễn phí"
        author_display = book.author or "Tác giả không rõ"
        return f"'{book.title}' của {author_display} ({price_display})"