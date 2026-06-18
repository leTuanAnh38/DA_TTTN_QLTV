"""
Cache abstraction layer - cho phép thay đổi cache backend dễ dàng
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class cho cache backend"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Lấy value từ cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, timeout: int) -> bool:
        """Đặt value vào cache"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Xóa key từ cache"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Xóa toàn bộ cache"""
        pass


class DjangoCacheBackend(CacheBackend):
    """Wrapper cho Django cache"""
    
    def __init__(self):
        from django.core.cache import cache
        self.cache = cache
    
    def get(self, key: str) -> Optional[Any]:
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"[CACHE] Error getting key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, timeout: int) -> bool:
        try:
            self.cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.error(f"[CACHE] Error setting key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self.cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"[CACHE] Error deleting key {key}: {str(e)}")
            return False
    
    def clear(self) -> bool:
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.error(f"[CACHE] Error clearing cache: {str(e)}")
            return False


class RedisBackend(CacheBackend):
    """Redis cache backend"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        try:
            import redis
            self.redis_client = redis.Redis(
                host=host, port=port, db=db, decode_responses=True
            )
            self.redis_client.ping()
            logger.info("[CACHE] Redis backend initialized")
        except Exception as e:
            logger.error(f"[CACHE] Failed to initialize Redis: {str(e)}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"[CACHE] Redis get error for {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, timeout: int) -> bool:
        try:
            self.redis_client.setex(key, timeout, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"[CACHE] Redis set error for {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"[CACHE] Redis delete error for {key}: {str(e)}")
            return False
    
    def clear(self) -> bool:
        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.error(f"[CACHE] Redis clear error: {str(e)}")
            return False


class MemoryBackend(CacheBackend):
    """In-memory cache backend (for testing/development)"""
    
    def __init__(self):
        self.store = {}
        self.timeouts = {}
        import time
        self._time = time.time
    
    def get(self, key: str) -> Optional[Any]:
        try:
            # Check if key exists and not expired
            if key in self.store:
                if key in self.timeouts:
                    if self._time() > self.timeouts[key]:
                        del self.store[key]
                        del self.timeouts[key]
                        return None
                return self.store[key]
            return None
        except Exception as e:
            logger.error(f"[CACHE] Memory get error for {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, timeout: int) -> bool:
        try:
            self.store[key] = value
            self.timeouts[key] = self._time() + timeout
            return True
        except Exception as e:
            logger.error(f"[CACHE] Memory set error for {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            if key in self.store:
                del self.store[key]
            if key in self.timeouts:
                del self.timeouts[key]
            return True
        except Exception as e:
            logger.error(f"[CACHE] Memory delete error for {key}: {str(e)}")
            return False
    
    def clear(self) -> bool:
        try:
            self.store.clear()
            self.timeouts.clear()
            return True
        except Exception as e:
            logger.error(f"[CACHE] Memory clear error: {str(e)}")
            return False


class CacheManager:
    """Manager để tạo và quản lý cache backend"""
    
    _backends = {
        'django': DjangoCacheBackend,
        'redis': RedisBackend,
        'memory': MemoryBackend,
    }
    
    @classmethod
    def create_backend(cls, backend_type: str, **kwargs) -> CacheBackend:
        """Tạo cache backend"""
        if backend_type not in cls._backends:
            raise ValueError(f"Unknown cache backend: {backend_type}")
        
        backend_class = cls._backends[backend_type]
        return backend_class(**kwargs)
    
    @classmethod
    def register_backend(cls, name: str, backend_class: type):
        """Đăng ký backend mới"""
        cls._backends[name] = backend_class
