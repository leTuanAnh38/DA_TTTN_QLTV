"""
Configuration module for Gemini Chat Service
Tập trung quản lý tất cả các config, constants, và settings
"""
from typing import Dict, Any
from dataclasses import dataclass
import logging


@dataclass
class ChatConfig:
    """Configuration cho Chat Service"""
    
    # API Settings
    GEMINI_MODEL: str = "gemini-2.5-flash"
    API_TEMPERATURE: float = 0.3
    RATE_LIMIT_SECONDS: int = 5
    
    # Thư viện Business Rules
    MAX_BORROW_PER_USER: int = 4
    BORROW_DURATION_DAYS: int = 14
    LATE_FEE_PER_DAY: int = 5000  # VNĐ
    PENALTY_POINTS_PER_DAY: int = 5
    BOOK_REPLACEMENT_PERCENT: float = 100.0
    
    # Cache Settings
    CACHE_TIMEOUT_SECONDS: int = 1800  # 30 phút
    CACHE_BACKEND: str = "django"  # 'django', 'redis', 'memory'
    
    # Shift Configuration
    SHIFTS: Dict[str, str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "[%(name)s] %(levelname)s - %(message)s"
    
    # Date Keywords
    DATE_KEYWORDS: Dict[str, int] = None
    
    # Inappropriate patterns (book validation)
    INAPPROPRIATE_BOOK_PATTERNS: list = None
    
    def __post_init__(self):
        """Initialize default values"""
        if self.SHIFTS is None:
            self.SHIFTS = {
                'SANG': 'Sáng (07:30-11:30)',
                'CHIEU': 'Chiều (13:00-17:00)'
            }
        
        if self.DATE_KEYWORDS is None:
            self.DATE_KEYWORDS = {
                'hôm nay': 0,
                'hôm nay': 0,
                'ngày mai': 1,
                'mai': 1,
                'ngày kia': 2,
                'kia': 2,
                'sáng nay': 0,
                'chiều nay': 0,
            }
        
        if self.INAPPROPRIATE_BOOK_PATTERNS is None:
            self.INAPPROPRIATE_BOOK_PATTERNS = [
                'con cu', 'lmao', 'haha', 'xxx', '123', 'test', 'spam',
                'bla', 'foo', 'bar', 'aaa', 'bbb', 'ccc', '...'
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            'gemini_model': self.GEMINI_MODEL,
            'api_temperature': self.API_TEMPERATURE,
            'max_borrow': self.MAX_BORROW_PER_USER,
            'borrow_days': self.BORROW_DURATION_DAYS,
            'late_fee': self.LATE_FEE_PER_DAY,
        }


def get_default_config() -> ChatConfig:
    """Get default configuration"""
    return ChatConfig()


def get_config_from_settings(django_settings) -> ChatConfig:
    """Load configuration from Django settings"""
    config = ChatConfig()
    
    # Override từ Django settings nếu có
    if hasattr(django_settings, 'CHAT_CONFIG'):
        for key, value in django_settings.CHAT_CONFIG.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return config
