// Chatbox Bubble & Chat Window
class ChatBox {
    constructor() {
        this.isOpen = sessionStorage.getItem('chat_isOpen') === 'true';
        this.isFirstOpen = true;  // Flag để check lần đầu mở chat
        this.init();
    }
    
    init() {
        this.injectStyles();
        this.createBubble();
        this.createChatWindow();
        this.attachEvents();
        
        // Restore open state on page load
        if (this.isOpen) {
            this.chatWindow.style.display = 'flex';
            this.chatWindow.offsetHeight;
            this.chatWindow.classList.add('open');
            this.loadHistoryOrGreeting();
        }
    }
    
    injectStyles() {
    // 1. Kiểm tra xem style đã được inject chưa để tránh rác DOM nếu hàm bị gọi nhiều lần
    if (document.getElementById('chat-widget-styles')) return;

    const style = document.createElement('style');
    style.id = 'chat-widget-styles';

    // 2. Gom nhóm CSS logic, sử dụng CSS Variables để dễ dàng đổi theme sau này
    style.textContent = `
        /* =========================================
           CSS VARIABLES (Dễ dàng tùy chỉnh Theme)
           ========================================= */
        :root {
            --chat-primary: #4f46e5;
            --chat-secondary: #7c3aed;
            --chat-gradient: linear-gradient(135deg, var(--chat-primary) 0%, var(--chat-secondary) 100%);
            --chat-bg-light: #f8fafc;
            --chat-text-dark: #1f2937;
            --chat-border: rgba(229, 231, 235, 0.8);
            --chat-font: 'Inter', 'Roboto', 'Open Sans', sans-serif;
            --chat-z-index: 10000;
        }

        /* =========================================
           1. CHAT BUBBLE (Nút mở chat)
           ========================================= */
        #chat-bubble {
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: var(--chat-gradient);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            cursor: grab;
            box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.4), 0 8px 10px -6px rgba(79, 70, 229, 0.4);
            z-index: var(--chat-z-index);
            user-select: none;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid rgba(255, 255, 255, 0.15);
        }
        #chat-bubble:active { cursor: grabbing; }
        #chat-bubble:hover {
            transform: scale(1.1) rotate(5deg);
            box-shadow: 0 20px 30px -10px rgba(79, 70, 229, 0.6);
        }

        /* =========================================
           2. CHAT WINDOW (Cửa sổ chat chính)
           ========================================= */
        #chat-window {
            position: fixed;
            bottom: 96px;
            right: 24px;
            width: 380px;
            height: 520px;
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            display: none;
            flex-direction: column;
            z-index: var(--chat-z-index);
            overflow: hidden;
            border: 1px solid var(--chat-border);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: translateY(20px) scale(0.95);
        }
        #chat-window.open {
            opacity: 1;
            transform: translateY(0) scale(1);
        }

        /* --- Header --- */
        .chat-header {
            background: var(--chat-gradient);
            color: white;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .chat-header-title {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: var(--chat-font);
        }
        .chat-header-status {
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.4);
            animation: chat-pulse 2s infinite;
        }
        #close-chat {
            background: rgba(255, 255, 255, 0.15);
            border: none;
            color: white;
            font-size: 14px;
            cursor: pointer;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        #close-chat:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: scale(1.05);
        }

        /* --- Messages Area --- */
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background-color: var(--chat-bg-light);
            scroll-behavior: smooth;
        }
        #messages::-webkit-scrollbar { width: 6px; }
        #messages::-webkit-scrollbar-track { background: transparent; }
        #messages::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 4px;
        }
        #messages::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

        .message-bubble {
            padding: 10px 16px;
            border-radius: 16px;
            max-width: 80%;
            font-size: 14px;
            line-height: 1.5;
            word-wrap: break-word;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            animation: chat-fadeInUp 0.2s ease-out forwards;
            font-family: var(--chat-font);
        }
        .message-bubble.user {
            background: var(--chat-gradient);
            color: white !important;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .message-bubble.bot {
            background: #ffffff;
            color: var(--chat-text-dark) !important;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
            border: 1px solid #e2e8f0;
        }

        /* --- Input Area --- */
        .chat-input-area {
            padding: 16px;
            display: flex;
            gap: 10px;
            border-top: 1px solid #f1f5f9;
            background: white;
            align-items: center;
        }
        #message-input {
            flex: 1;
            border: 1px solid #e2e8f0;
            border-radius: 24px;
            padding: 10px 16px;
            font-size: 14px;
            font-family: var(--chat-font);
            outline: none;
            transition: all 0.2s;
            color: var(--chat-text-dark);
            background-color: var(--chat-bg-light);
        }
        #message-input:focus {
            border-color: var(--chat-primary);
            background-color: #ffffff;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
        }
        #send-btn {
            background: var(--chat-gradient);
            color: white;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
        }
        #send-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(79, 70, 229, 0.35);
        }
        #send-btn:active { transform: scale(0.95); }

        /* =========================================
           3. INDICATORS & ANIMATIONS
           ========================================= */
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 6px 4px;
        }
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background-color: #94a3b8;
            border-radius: 50%;
            display: inline-block;
            animation: chat-bounce 1.4s infinite ease-in-out both;
        }
        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes chat-bounce {
            0%, 80%, 100% { transform: scale(0); opacity: 0.3; } 
            40% { transform: scale(1.0); opacity: 1; }
        }
        @keyframes chat-pulse {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        @keyframes chat-fadeInUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    
    document.head.appendChild(style);
    }
    
    createBubble() {
        const bubble = document.createElement('div');
        bubble.id = 'chat-bubble';
        bubble.innerHTML = '<i class="fas fa-comment-dots"></i>';
        document.body.appendChild(bubble);
        this.bubble = bubble;
        this.makeDraggable(bubble);
    }
    
    createChatWindow() {
        const window = document.createElement('div');
        window.id = 'chat-window';
        
        window.innerHTML = `
            <div class="chat-header">
                <div class="chat-header-title">
                    <i class="fas fa-robot"></i>
                    <span>Trợ lý Thư viện</span>
                    <span class="chat-header-status"></span>
                </div>
                <button id="close-chat">✕</button>
            </div>
            <div id="messages"></div>
            <div class="chat-input-area">
                <input id="message-input" type="text" placeholder="Nhập tin nhắn..." autocomplete="off">
                <button id="send-btn">
                    <i class="fas fa-paper-plane"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(window);
        this.chatWindow = window;
    }
    
    attachEvents() {
        this.bubble.addEventListener('click', (e) => {
            if (this.bubble.classList.contains('was-dragged')) {
                return;
            }
            this.toggleChat();
        });
        document.getElementById('close-chat').addEventListener('click', () => this.toggleChat());
        document.getElementById('send-btn').addEventListener('click', () => this.sendMessage());
        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }
    
    toggleChat() {
        this.isOpen = !this.isOpen;
        sessionStorage.setItem('chat_isOpen', this.isOpen);
        if (this.isOpen) {
            this.chatWindow.style.display = 'flex';
            // Force reflow
            this.chatWindow.offsetHeight;
            this.chatWindow.classList.add('open');
            this.loadHistoryOrGreeting();
        } else {
            this.chatWindow.classList.remove('open');
            setTimeout(() => {
                if (!this.isOpen) {
                    this.chatWindow.style.display = 'none';
                }
            }, 300);
        }
    }
    
    loadHistoryOrGreeting() {
        if (!this.isFirstOpen) return;
        this.isFirstOpen = false;
        
        this.showTypingIndicator();
        
        fetch('/api/chat/history/', {
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken')
            }
        })
        .then(r => r.json())
        .then(data => {
            this.hideTypingIndicator();
            if (data.status === 'success' && data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    const role = msg.role.toLowerCase();
                    this.displayMessage(msg.message, role);
                });
            } else {
                // Nếu chưa có lịch sử, tải tin nhắn chào mừng (greeting)
                this.showTypingIndicator();
                fetch('/api/chat/greeting/', {
                    headers: {
                        'X-CSRFToken': this.getCookie('csrftoken')
                    }
                })
                .then(r => r.json())
                .then(greetData => {
                    this.hideTypingIndicator();
                    this.displayMessage(greetData.message, 'bot');
                })
                .catch(err => {
                    this.hideTypingIndicator();
                });
            }
        })
        .catch(err => {
            this.hideTypingIndicator();
            this.displayMessage("Xin lỗi, đã xảy ra lỗi kết nối.", 'bot');
        });
    }
    
    sendMessage() {
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        if (!message) return;
        
        input.value = '';
        this.displayMessage(message, 'user');
        
        this.showTypingIndicator();
        
        fetch('/api/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken')
            },
            body: JSON.stringify({ message: message })
        })
        .then(r => r.json())
        .then(data => {
            this.hideTypingIndicator();
            if (data.status === 'success') {
                this.displayMessage(data.message, 'bot');
            } else {
                this.displayMessage(data.message || "Đã xảy ra lỗi.", 'bot');
            }
        })
        .catch(err => {
            this.hideTypingIndicator();
            this.displayMessage("Xin lỗi, không thể kết nối đến máy chủ.", 'bot');
        });
    }
    
    displayMessage(text, role) {
        const messagesDiv = document.getElementById('messages');
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-bubble ${role}`;
        msgDiv.textContent = text;
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    showTypingIndicator() {
        if (document.getElementById('typing-indicator')) return;
        
        const messagesDiv = document.getElementById('messages');
        const indicatorDiv = document.createElement('div');
        indicatorDiv.id = 'typing-indicator';
        indicatorDiv.className = 'message-bubble bot';
        indicatorDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        messagesDiv.appendChild(indicatorDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    makeDraggable(element) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        let isMove = false;
        element.onmousedown = (e) => {
            // Convert bottom/right style properties to top/left values before dragging
            const rect = element.getBoundingClientRect();
            element.style.bottom = 'auto';
            element.style.right = 'auto';
            element.style.top = rect.top + 'px';
            element.style.left = rect.left + 'px';
            
            pos3 = e.clientX;
            pos4 = e.clientY;
            isMove = false;
            
            const onMouseMove = (e) => {
                const dx = e.clientX - pos3;
                const dy = e.clientY - pos4;
                if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
                    isMove = true;
                }
                pos1 = pos3 - e.clientX;
                pos2 = pos4 - e.clientY;
                pos3 = e.clientX;
                pos4 = e.clientY;
                
                let newTop = element.offsetTop - pos2;
                let newLeft = element.offsetLeft - pos1;
                
                // Restrict positioning to prevent going off-screen
                const maxTop = window.innerHeight - element.offsetHeight;
                const maxLeft = window.innerWidth - element.offsetWidth;
                
                newTop = Math.max(0, Math.min(newTop, maxTop));
                newLeft = Math.max(0, Math.min(newLeft, maxLeft));
                
                element.style.top = newTop + "px";
                element.style.left = newLeft + "px";
            };
            
            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                if (isMove) {
                    element.classList.add('was-dragged');
                    setTimeout(() => element.classList.remove('was-dragged'), 50);
                }
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        };
    }
    
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

document.addEventListener('DOMContentLoaded', () => new ChatBox());