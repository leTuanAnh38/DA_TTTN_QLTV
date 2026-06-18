"""
Intent handler abstraction - plugin architecture cho phép mở rộng xử lý intent
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result từ intent handler"""
    has_intent: bool
    intent_type: str
    confidence: float
    data: Dict[str, Any]
    message: Optional[str] = None


class IntentHandler(ABC):
    """Abstract base class cho intent handler"""
    
    @property
    @abstractmethod
    def intent_type(self) -> str:
        """Type của intent này"""
        pass
    
    @abstractmethod
    def detect(self, message: str) -> IntentResult:
        """Detect xem có intent này trong message không"""
        pass
    
    @abstractmethod
    def handle(self, user, message: str, data: Dict[str, Any]) -> Optional[str]:
        """Handle intent này"""
        pass


class BorrowIntentHandler(IntentHandler):
    """Handler cho borrow intent"""
    
    @property
    def intent_type(self) -> str:
        return "borrow"
    
    # Từ khóa mượn sách
    BORROW_KEYWORDS = {
        'mượn', 'borrow', 'borrowed', 'muốn mượn', 'có thể mượn',
        'mua', 'buy', 'order', 'đặt', 'register'
    }
    
    def detect(self, message: str) -> IntentResult:
        """Detect borrow intent"""
        msg_lower = message.lower()
        
        # Check keywords
        has_borrow_keyword = any(kw in msg_lower for kw in self.BORROW_KEYWORDS)
        
        if not has_borrow_keyword:
            return IntentResult(
                has_intent=False,
                intent_type=self.intent_type,
                confidence=0,
                data={}
            )
        
        # Extract data
        data = {
            'book_keywords': self._extract_keywords(message),
            'book_title_hint': self._extract_book_title(message),
            'preferred_date': None,
            'preferred_shift': None,
        }
        
        return IntentResult(
            has_intent=True,
            intent_type=self.intent_type,
            confidence=0.9,
            data=data
        )
    
    def handle(self, user, message: str, data: Dict[str, Any]) -> Optional[str]:
        """Handle borrow - should be implemented by the service"""
        logger.info(f"[BORROW INTENT] Handling for user {user.username}")
        return None
    
    def _extract_keywords(self, message: str) -> List[str]:
        """Extract search keywords"""
        stop_words = {
            'có', 'sách', 'nào', 'về', 'không', 'tìm', 'cho', 'mình',
            'cuốn', 'thể', 'loại', 'muốn', 'đọc', 'free', 'miễn', 'phí'
        }
        keywords = [w for w in message.lower().split() 
                   if w not in stop_words and len(w) > 2]
        return keywords
    
    def _extract_book_title(self, message: str) -> Optional[str]:
        """Try to extract book title from message"""
        # Simple heuristic: look for quoted text
        import re
        matches = re.findall(r"['\"]([^'\"]+)['\"]", message)
        return matches[0] if matches else None


class SearchIntentHandler(IntentHandler):
    """Handler cho search intent"""
    
    @property
    def intent_type(self) -> str:
        return "search"
    
    SEARCH_KEYWORDS = {
        'tìm', 'search', 'find', 'có', 'giới thiệu',
        'recommend', 'gợi ý', 'sách gì'
    }
    
    def detect(self, message: str) -> IntentResult:
        """Detect search intent"""
        msg_lower = message.lower()
        has_search_keyword = any(kw in msg_lower for kw in self.SEARCH_KEYWORDS)
        
        if not has_search_keyword:
            return IntentResult(
                has_intent=False,
                intent_type=self.intent_type,
                confidence=0,
                data={}
            )
        
        # Extract search terms
        keywords = [w for w in msg_lower.split() if len(w) > 2]
        
        return IntentResult(
            has_intent=True,
            intent_type=self.intent_type,
            confidence=0.8,
            data={'search_terms': keywords}
        )
    
    def handle(self, user, message: str, data: Dict[str, Any]) -> Optional[str]:
        """Handle search - should be implemented by the service"""
        logger.info(f"[SEARCH INTENT] Handling for user {user.username}")
        return None


class HelpIntentHandler(IntentHandler):
    """Handler cho help/information intent"""
    
    @property
    def intent_type(self) -> str:
        return "help"
    
    HELP_KEYWORDS = {
        'cách', 'làm sao', 'help', 'hướng dẫn', 'quy tắc',
        'trả sách', 'phạt', 'mất sách', 'đền'
    }
    
    def detect(self, message: str) -> IntentResult:
        """Detect help intent"""
        msg_lower = message.lower()
        has_help_keyword = any(kw in msg_lower for kw in self.HELP_KEYWORDS)
        
        if not has_help_keyword:
            return IntentResult(
                has_intent=False,
                intent_type=self.intent_type,
                confidence=0,
                data={}
            )
        
        return IntentResult(
            has_intent=True,
            intent_type=self.intent_type,
            confidence=0.7,
            data={'query': message}
        )
    
    def handle(self, user, message: str, data: Dict[str, Any]) -> Optional[str]:
        """Handle help - should be implemented by the service"""
        logger.info(f"[HELP INTENT] Handling for user {user.username}")
        return None


class IntentRegistry:
    """Registry để quản lý intent handlers"""
    
    def __init__(self):
        self.handlers: Dict[str, IntentHandler] = {}
        self._default_handlers = [
            BorrowIntentHandler(),
            SearchIntentHandler(),
            HelpIntentHandler(),
        ]
        
        # Register default handlers
        for handler in self._default_handlers:
            self.register(handler)
    
    def register(self, handler: IntentHandler) -> None:
        """Register intent handler"""
        self.handlers[handler.intent_type] = handler
        logger.info(f"[INTENT] Registered handler: {handler.intent_type}")
    
    def detect(self, message: str) -> List[IntentResult]:
        """Detect all intents in message"""
        results = []
        for handler in self.handlers.values():
            result = handler.detect(message)
            if result.has_intent:
                results.append(result)
        
        # Sort by confidence
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results
    
    def get_handler(self, intent_type: str) -> Optional[IntentHandler]:
        """Get handler for specific intent type"""
        return self.handlers.get(intent_type)
    
    def unregister(self, intent_type: str) -> bool:
        """Unregister intent handler"""
        if intent_type in self.handlers:
            del self.handlers[intent_type]
            logger.info(f"[INTENT] Unregistered handler: {intent_type}")
            return True
        return False
