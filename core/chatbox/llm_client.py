"""
API Client abstraction - cho phép thay đổi LLM model dễ dàng
Hỗ trợ Gemini, OpenAI, Anthropic, v.v...
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)


class Message:
    """Represent a message in conversation"""
    
    def __init__(self, role: str, content: str):
        self.role = role  # 'user', 'assistant', 'system'
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {'role': self.role, 'content': self.content}


class LLMClient(ABC):
    """Abstract base class cho LLM clients"""
    
    @abstractmethod
    def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if API is available"""
        pass


class GeminiClient(LLMClient):
    """Google Gemini LLM Client"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        try:
            import google.genai as genai
            from google.genai import types
            
            self.genai = genai
            self.types = types
            self.client = genai.Client(api_key=api_key)
            self.model = model
            self._is_available = True
            logger.info(f"[GEMINI] Client initialized with model: {model}")
        except ImportError:
            logger.error("[GEMINI] google.genai not installed")
            self._is_available = False
        except Exception as e:
            logger.error(f"[GEMINI] Initialization error: {str(e)}")
            self._is_available = False
    
    def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                contents.append(self.types.Content(
                    role=msg.role,
                    parts=[self.types.Part.from_text(text=msg.content)]
                ))
            
            # Generate response
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=self.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                )
            )
            
            logger.debug(f"[GEMINI] Generated response - Length: {len(response.text)}")
            return response.text
        
        except Exception as e:
            logger.error(f"[GEMINI] Generation error: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        return self._is_available


class OpenAIClient(LLMClient):
    """OpenAI GPT Client"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        try:
            import openai
            openai.api_key = api_key
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model
            self._is_available = True
            logger.info(f"[OPENAI] Client initialized with model: {model}")
        except ImportError:
            logger.error("[OPENAI] openai not installed")
            self._is_available = False
        except Exception as e:
            logger.error(f"[OPENAI] Initialization error: {str(e)}")
            self._is_available = False
    
    def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            # Prepare messages
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})
            
            api_messages.extend([msg.to_dict() for msg in messages])
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            logger.debug(f"[OPENAI] Generated response")
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"[OPENAI] Generation error: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        return self._is_available


class AnthropicClient(LLMClient):
    """Anthropic Claude Client"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model
            self._is_available = True
            logger.info(f"[ANTHROPIC] Client initialized with model: {model}")
        except ImportError:
            logger.error("[ANTHROPIC] anthropic not installed")
            self._is_available = False
        except Exception as e:
            logger.error(f"[ANTHROPIC] Initialization error: {str(e)}")
            self._is_available = False
    
    def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            api_messages = [msg.to_dict() for msg in messages]
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or 1024,
                system=system_prompt,
                messages=api_messages,
                temperature=temperature,
            )
            
            logger.debug(f"[ANTHROPIC] Generated response")
            return response.content[0].text
        
        except Exception as e:
            logger.error(f"[ANTHROPIC] Generation error: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        return self._is_available


class RateLimitedClient(LLMClient):
    """Wrapper để add rate limiting vào bất kỳ LLM client nào"""
    
    def __init__(self, client: LLMClient, rate_limit_seconds: int = 5):
        self.client = client
        self.rate_limit_seconds = rate_limit_seconds
        self.last_call_time = 0
    
    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_seconds:
            sleep_time = self.rate_limit_seconds - elapsed
            logger.debug(f"[RATE_LIMIT] Waiting {sleep_time:.2f}s")
            time.sleep(sleep_time)
    
    def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        self._wait_for_rate_limit()
        result = self.client.generate(messages, system_prompt, temperature, max_tokens)
        self.last_call_time = time.time()
        return result
    
    def is_available(self) -> bool:
        return self.client.is_available()


class LLMClientFactory:
    """Factory để tạo LLM clients"""
    
    _clients = {
        'gemini': GeminiClient,
        'openai': OpenAIClient,
        'anthropic': AnthropicClient,
    }
    
    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        model: str,
        rate_limit: Optional[int] = None,
    ) -> LLMClient:
        """Create LLM client"""
        if provider not in cls._clients:
            raise ValueError(f"Unknown LLM provider: {provider}")
        
        client_class = cls._clients[provider]
        client = client_class(api_key, model)
        
        # Wrap with rate limiting if specified
        if rate_limit:
            client = RateLimitedClient(client, rate_limit)
        
        return client
    
    @classmethod
    def register_client(cls, name: str, client_class: type):
        """Register custom LLM client"""
        cls._clients[name] = client_class
