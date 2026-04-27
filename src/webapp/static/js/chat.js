/* src/webapp/static/js/chat.js */
function chatApp() {
    const wsUrl = (window.location.protocol === 'https:' ? 'wss:' : 'ws:')
        + '//' + window.location.host + '/chat/ws';

    return {
        sidebarOpen: true,
        activeTab: 'chat',
        messages: [],
        newMessage: '',
        agentStatus: 'online',
        agentStatusText: 'System Ready',
        settings: {
            autonomous: true,
            maxRetries: 3,
            reflectionThreshold: 3,
            graphPersist: true,
        },
        ws: null,

        init() {
            this.connect();
            this.loadMessages();
        },

        connect() {
            try {
                this.ws = new WebSocket(wsUrl);
                this.ws.onopen = () => {
                    this.agentStatus = 'online';
                    this.agentStatusText = 'Connected';
                };
                this.ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    this.messages.push(msg);
                    this.scrollToBottom();
                };
                this.ws.onclose = () => {
                    this.agentStatus = 'offline';
                    this.agentStatusText = 'Disconnected';
                    setTimeout(() => this.connect(), 3000);
                };
                this.ws.onerror = () => {
                    this.agentStatus = 'offline';
                    this.agentStatusText = 'Connection Error';
                };
            } catch (e) {
                console.error('WebSocket error:', e);
            }
        },

        async loadMessages() {
            try {
                const resp = await fetch('/chat/messages');
                if (!resp.ok) return;
                const data = await resp.json();
                if (data.messages && Array.isArray(data.messages)) {
                    this.messages = data.messages;
                    this.scrollToBottom();
                }
            } catch (e) {
                console.error('Failed to load messages:', e);
            }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            if (!text) return;
            this.newMessage = '';

            const msg = {
                role: 'user',
                content: text,
                code_blocks: [],
                agent_status: ''
            };

            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify(msg));
            } else {
                await fetch('/chat/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(msg)
                });
                this.messages.push(msg);
                this.scrollToBottom();
            }
        },

        renderContent(msg) {
            let html = msg.content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html = html.replace(
                /```(\w+)?\n([\s\S]*?)```/g,
                (match, lang, code) => {
                    if (!msg.code_blocks) msg.code_blocks = [];
                    const id = msg.id + '_' + (msg.code_blocks.length + 1);
                    msg.code_blocks.push({ id, language: lang || 'code', code });
                    return '<em>Code attached below</em>';
                }
            );
            return html;
        },

        copyCode(block) {
            navigator.clipboard.writeText(block.code).catch(() => {});
        },

        scrollToBottom() {
            this.$nextTick(() => {
                const el = document.getElementById('messages');
                if (el) el.scrollTop = el.scrollHeight;
            });
        }
    };
}
