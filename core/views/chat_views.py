from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from core.models import ChatMessage
from core.chatbox import AdvancedGeminiChatService

logger = logging.getLogger(__name__)

@login_required
@require_POST
@csrf_exempt
def chat_message_api(request):
    """API endpoint nhận tin nhắn từ frontend - CÓ HỖ TRỢ MƯỢN SÁCH TỰ ĐỘNG"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        logger.debug(f"[CHAT API] Received message from {request.user.username}: '{user_message}'")
        
        if not user_message:
            return JsonResponse({'error': 'Message không được để trống'}, status=400)
        
        # Lưu tin nhắn của user
        ChatMessage.objects.create(
            user=request.user,
            message=user_message,
            role='USER'
        )
        
        # Gọi Advanced Gemini Service - TỰ ĐỘNG XỬ LÝ BORROW INTENT BÊN TRONG
        service = AdvancedGeminiChatService()
        logger.debug(f"[CHAT API] Calling AdvancedGeminiChatService...")
        bot_response = service.chat(user_message, request.user, request=request)
        
        # Lưu phản hồi của bot
        ChatMessage.objects.create(
            user=request.user,
            message=bot_response,
            role='BOT'
        )
        
        logger.debug(f"[CHAT API] Response saved - length: {len(bot_response)}")
        
        return JsonResponse({
            'status': 'success',
            'message': bot_response
        })
    
    except Exception as e:
        logger.error(f"[CHAT API] Error: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_chat_history(request):
    """Lấy lịch sử chat (25 tin nhắn mới nhất)"""
    messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:25]
    messages_list = []
    for msg in reversed(messages):
        messages_list.append({
            'role': msg.role.lower(),
            'message': msg.message,
            'created_at': msg.created_at
        })
    return JsonResponse({
        'status': 'success',
        'messages': messages_list
    })

@login_required
def get_chat_greeting(request):
    """Lấy greeting message khi mở chat lần đầu"""
    first_name = request.user.first_name or "bạn"
    greeting = f"""Xin chào {first_name}! 👋 Tôi là trợ lý ảo của thư viện Alovu. 📚

✨ Tôi có thể giúp bạn:
• Tìm và mượn sách
• Giải đáp các quy định thư viện
• Cung cấp gợi ý sách hay

📝 **Cách mượn sách qua chat** (để hệ thống hoạt động tốt nhất):
1️⃣ Nói: "Hãy mượn [tên sách]"
2️⃣ Chọn cuốn sách (1, 2 hoặc 3)
3️⃣ Trả lời: "ca [sáng/chiều] [DD/MM/YYYY]"
   Ví dụ: "sáng ngày 21/04/2026" hoặc "ca chiều 21/04/2026"

💡 Hoặc nói trực tiếp: "Mượn [tên sách] sáng ngày 21/04/2026"

Bạn cần giúp gì nào? 😊"""
    return JsonResponse({'message': greeting})