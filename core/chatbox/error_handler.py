"""
Advanced error handling và fallback strategies
"""
from typing import Optional, Callable, Any
from functools import wraps
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Base exception cho Chat Service"""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class APIError(ChatServiceError):
    """API call error"""
    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, error_code=f"API_{provider.upper()}_ERROR")
        self.provider = provider


class CacheError(ChatServiceError):
    """Cache operation error"""
    def __init__(self, message: str):
        super().__init__(message, error_code="CACHE_ERROR")


class ValidationError(ChatServiceError):
    """Input validation error"""
    def __init__(self, message: str, field: str = ""):
        super().__init__(message, error_code="VALIDATION_ERROR")
        self.field = field


class DatabaseError(ChatServiceError):
    """Database operation error"""
    def __init__(self, message: str):
        super().__init__(message, error_code="DATABASE_ERROR")


class ErrorHandler:
    """Centralized error handling"""
    
    # Fallback responses cho khác nhau error types
    FALLBACK_RESPONSES = {
        'API_ERROR': "💡 Hệ thống đang hơi quá tải một chút. Bạn vui lòng thử lại sau vài giây nhé!",
        'CACHE_ERROR': "⚠️ Lỗi kỹ thuật tạm thời. Vui lòng thử lại.",
        'VALIDATION_ERROR': "❌ Dữ liệu không hợp lệ. Vui lòng kiểm tra lại.",
        'DATABASE_ERROR': "⚠️ Lỗi hệ thống. Vui lòng liên hệ quản trị viên.",
        'UNKNOWN_ERROR': "👋 Có lỗi gì đó xảy ra. Vui lòng thử lại sau.",
    }
    
    def __init__(self):
        self.error_log = []
    
    def handle_error(self, error: Exception, context: str = "") -> str:
        """Handle error và return fallback response"""
        
        # Log error
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'message': str(error),
            'context': context,
        }
        self.error_log.append(error_info)
        
        logger.error(
            f"[ERROR] {error_info['error_type']}: {error_info['message']} | Context: {context}",
            exc_info=True
        )
        
        # Determine error code
        if isinstance(error, ChatServiceError):
            error_code = error.error_code
        else:
            error_code = "UNKNOWN_ERROR"
        
        # Get fallback response
        fallback = self.FALLBACK_RESPONSES.get(error_code, self.FALLBACK_RESPONSES['UNKNOWN_ERROR'])
        return fallback
    
    def get_error_summary(self, limit: int = 10) -> str:
        """Get summary của recent errors"""
        recent = self.error_log[-limit:]
        summary = f"Recent errors ({len(recent)}):\n"
        for err in recent:
            summary += f"• {err['timestamp']}: {err['error_type']} - {err['message']}\n"
        return summary
    
    def clear_error_log(self):
        """Clear error log"""
        self.error_log.clear()


def safe_api_call(func: Callable, timeout: int = 10, retries: int = 2) -> Callable:
    """Decorator để safe API calls với retry logic"""
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        
        last_error = None
        for attempt in range(retries):
            try:
                logger.debug(f"[SAFE_API] Attempt {attempt + 1}/{retries} for {func.__name__}")
                return func(*args, **kwargs)
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[SAFE_API] Attempt {attempt + 1} failed for {func.__name__}: {str(e)}"
                )
                
                # Wait before retry
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.debug(f"[SAFE_API] Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        # All retries failed
        logger.error(f"[SAFE_API] All {retries} attempts failed for {func.__name__}")
        raise APIError(f"API call failed after {retries} attempts", provider=func.__name__) from last_error
    
    return wrapper


def handle_exceptions(error_handler: ErrorHandler, context: str = "") -> Callable:
    """Decorator để handle exceptions với error handler"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Exception in {func.__name__}: {str(e)}", exc_info=True)
                return error_handler.handle_error(e, context=f"{func.__name__} - {context}")
        
        return wrapper
    
    return decorator


class RetryStrategy:
    """Retry strategies cho operations"""
    
    @staticmethod
    def exponential_backoff(func: Callable, max_retries: int = 3) -> Any:
        """Retry với exponential backoff"""
        import time
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = 2 ** attempt
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}")
                time.sleep(wait_time)
    
    @staticmethod
    def linear_backoff(func: Callable, max_retries: int = 3, delay: int = 1) -> Any:
        """Retry với linear backoff"""
        import time
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = delay * (attempt + 1)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}")
                time.sleep(wait_time)


class CircuitBreaker:
    """Circuit breaker pattern cho prevent cascading failures"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function với circuit breaker"""
        
        # Check if circuit is open
        if self.is_open:
            import time
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout:
                logger.info("[CIRCUIT_BREAKER] Attempting to close circuit")
                self.is_open = False
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is OPEN - too many failures")
        
        try:
            result = func(*args, **kwargs)
            # Reset on success
            self.failure_count = 0
            return result
        
        except Exception as e:
            import time
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(
                    f"[CIRCUIT_BREAKER] Opening circuit after {self.failure_count} failures"
                )
            
            raise
    
    def reset(self):
        """Reset circuit breaker"""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None
        logger.info("[CIRCUIT_BREAKER] Circuit reset")
