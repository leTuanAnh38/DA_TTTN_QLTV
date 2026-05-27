// Chatbox Bubble & Chat Window
class ChatBox {
    constructor() {
        this.isOpen = false;
        this.isFirstOpen = true;  // Flag để check lần đầu mở chat
        this.init();
    }
    
    init() {
        this.createBubble();
        this.createChatWindow();
        this.attachEvents();
    }
    
    createBubble() {
        const bubble = document.createElement('div');
        bubble.id = 'chat-bubble';
        bubble.innerHTML = '💬';
        bubble.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            cursor: move;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 999;
            user-select: none;
            transition: transform 0.2s;
        `;
        bubble.onmouseover = () => bubble.style.transform = 'scale(1.1)';
        bubble.onmouseout = () => bubble.style.transform = 'scale(1)';
        document.body.appendChild(bubble);
        this.bubble = bubble;
        this.makeDraggable(bubble);
    }
    
    createChatWindow() {
        const window = document.createElement('div');
        window.id = 'chat-window';
        window.style.cssText = `
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 380px;
            height: 500px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 5px 40px rgba(0,0,0,0.16);
            display: none;
            flex-direction: column;
            z-index: 999;
        `;
        
        window.innerHTML = `
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px; border-radius: 12px 12px 0 0; display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; font-size: 16px;">📚 Trợ lý Thư Viện</h3>
                <button id="close-chat" style="background: none; border: none; color: white; font-size: 20px; cursor: pointer;">✕</button>
            </div>
            <div id="messages" style="flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;"></div>
            <div style="padding: 12px; display: flex; gap: 8px; border-top: 1px solid #eee;">
                <input id="message-input" type="text" placeholder="Nhập tin nhắn..." style="flex: 1; border: 1px solid #ddd; border-radius: 20px; padding: 8px 12px; font-size: 14px;">
                <button id="send-btn" style="background: #667eea; color: white; border: none; border-radius: 50%; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center;">➤</button>
            </div>
        `;
        
        document.body.appendChild(window);
        this.chatWindow = window;
    }
    
    attachEvents() {
        this.bubble.addEventListener('click', () => this.toggleChat());
        document.getElementById('close-chat').addEventListener('click', () => this.toggleChat());
        document.getElementById('send-btn').addEventListener('click', () => this.sendMessage());
        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }
    
    toggleChat() {
        this.isOpen = !this.isOpen;
        this.chatWindow.style.display = this.isOpen ? 'flex' : 'none';
        
        // Lần đầu mở chat, gửi greeting message
        if (this.isOpen && this.isFirstOpen) {
            this.isFirstOpen = false;
            fetch('/api/chat/greeting/', {
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                }
            })
            .then(r => r.json())
            .then(data => {
                this.displayMessage(data.message, 'bot');
            });
        }
    }
    
    sendMessage() {
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        if (!message) return;
        
        input.value = '';
        this.displayMessage(message, 'user');
        
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
            if (data.status === 'success') {
                this.displayMessage(data.message, 'bot');
            }
        });
    }
    
    displayMessage(text, role) {
        const messagesDiv = document.getElementById('messages');
        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = `
            padding: 8px 12px;
            border-radius: 12px;
            max-width: 80%;
            word-wrap: break-word;
            ${role === 'user' ? 'background: #667eea; color: white; align-self: flex-end;' : 'background: #f1f1f1; color: black; align-self: flex-start;'}
        `;
        msgDiv.textContent = text;
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    makeDraggable(element) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        element.onmousedown = (e) => {
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = () => document.onmousemove = null;
            document.onmousemove = (e) => {
                pos1 = pos3 - e.clientX;
                pos2 = pos4 - e.clientY;
                pos3 = e.clientX;
                pos4 = e.clientY;
                element.style.top = (element.offsetTop - pos2) + "px";
                element.style.left = (element.offsetLeft - pos1) + "px";
            };
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

// Khởi tạo khi DOM ready
document.addEventListener('DOMContentLoaded', () => new ChatBox());