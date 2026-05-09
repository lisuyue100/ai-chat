from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import base64
import json
from openai import OpenAI
from typing import List, Dict

# =========================
# 初始化 FastAPI
# =========================
app = FastAPI()

# =========================
# 初始化 OpenAI 客户端
# =========================
client = OpenAI(
    api_key="ak_2gh9R66vc1nr7x04if5fr8uo8MP3s",
    base_url="https://api.longcat.chat/openai"
)

# =========================
# 全局对话历史
# =========================
conversation_history: List[Dict] = [
    {
        "role": "system",
        "content": [
            {"type": "text", "text": "你是一个可爱的语音助手"}
        ]
    }
]

# =========================
# HTML 前端
# =========================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 语音聊天</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            width: 100%;
            max-width: 800px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            height: 90vh;
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f5f5f5;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .message {
            display: flex;
            gap: 10px;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .message.user {
            justify-content: flex-end;
        }

        .message.assistant {
            justify-content: flex-start;
        }

        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 15px;
            word-wrap: break-word;
            line-height: 1.5;
            font-size: 14px;
        }

        .message.user .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 5px;
        }

        .message.assistant .message-content {
            background: #e0e0e0;
            color: #333;
            border-bottom-left-radius: 5px;
        }

        .audio-button {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.3s;
        }

        .audio-button:hover {
            background: #764ba2;
        }

        .audio-button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .input-area {
            padding: 20px;
            background: white;
            border-top: 1px solid #ddd;
            display: flex;
            gap: 10px;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
        }

        .input-wrapper {
            flex: 1;
            display: flex;
            gap: 10px;
        }

        input[type="text"] {
            flex: 1;
            border: 2px solid #ddd;
            border-radius: 25px;
            padding: 12px 20px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s;
        }

        input[type="text"]:focus {
            border-color: #667eea;
        }

        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            padding: 12px 30px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .loading {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #667eea;
            font-size: 14px;
        }

        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .status {
            padding: 10px 20px;
            text-align: center;
            font-size: 12px;
            color: #999;
            background: #f5f5f5;
        }

        audio {
            width: 100%;
            max-width: 300px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🎤 AI 语音聊天助手</div>
        
        <div class="chat-area" id="chatArea">
            <div class="status">等待输入...</div>
        </div>

        <div class="input-area">
            <div class="input-wrapper">
                <input 
                    type="text" 
                    id="messageInput" 
                    placeholder="输入你的问题..."
                    autocomplete="off"
                >
                <button id="sendBtn" onclick="sendMessage()">发送</button>
            </div>
        </div>
    </div>

    <script>
        const messageInput = document.getElementById('messageInput');
        const chatArea = document.getElementById('chatArea');
        const sendBtn = document.getElementById('sendBtn');
        let ws = null;
        let isConnected = false;

        // =========================
        // WebSocket 连接
        // =========================
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = function() {
                isConnected = true;
                console.log('WebSocket 已连接');
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);

                if (data.type === 'text') {
                    addOrUpdateMessage(data.content, 'assistant', data.message_id);
                } else if (data.type === 'audio') {
                    addAudioToMessage(data.message_id, data.audio_data);
                } else if (data.type === 'done') {
                    console.log('对话完成');
                    enableInput();
                } else if (data.type === 'error') {
                    addErrorMessage(data.error);
                    enableInput();
                }
            };

            ws.onerror = function(error) {
                console.error('WebSocket 错误:', error);
                addErrorMessage('连接错误，请刷新页面');
            };

            ws.onclose = function() {
                isConnected = false;
                console.log('WebSocket 已断开');
                setTimeout(connectWebSocket, 3000);
            };
        }

        // =========================
        // 发送消息
        // =========================
        function sendMessage() {
            const text = messageInput.value.trim();
            if (!text) return;

            if (!isConnected) {
                addErrorMessage('未连接到服务器，请稍候...');
                return;
            }

            // 清空输入
            messageInput.value = '';
            disableInput();

            // 显示用户消息
            addMessage(text, 'user');

            // 发送到后端
            ws.send(JSON.stringify({
                type: 'message',
                content: text
            }));
        }

        // =========================
        // 添加消息到 DOM
        // =========================
        function addMessage(text, role) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = text;
            
            messageDiv.appendChild(contentDiv);
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        // =========================
        // 添加或更新 AI 消息
        // =========================
        function addOrUpdateMessage(text, role, messageId) {
            let messageElement = document.getElementById(messageId);

            if (!messageElement) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${role}`;
                messageDiv.id = messageId;
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.id = `${messageId}-content`;
                contentDiv.textContent = text;
                
                messageDiv.appendChild(contentDiv);
                chatArea.appendChild(messageDiv);
            } else {
                const contentDiv = document.getElementById(`${messageId}-content`);
                contentDiv.textContent += text;
            }

            chatArea.scrollTop = chatArea.scrollHeight;
        }

        // =========================
        // 添加音频到消息
        // =========================
        function addAudioToMessage(messageId, audioBase64) {
            let messageElement = document.getElementById(messageId);

            if (messageElement) {
                const audioDiv = document.createElement('div');
                audioDiv.style.marginTop = '10px';
                
                const audio = document.createElement('audio');
                audio.controls = true;
                audio.style.maxWidth = '100%';
                audio.style.borderRadius = '8px';
                
                const audioBlob = base64ToBlob(audioBase64, 'audio/pcm');
                const audioUrl = URL.createObjectURL(audioBlob);
                audio.src = audioUrl;
                
                audioDiv.appendChild(audio);
                messageElement.appendChild(audioDiv);
            }
        }

        // =========================
        // 添加错误消息
        // =========================
        function addErrorMessage(error) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            messageDiv.style.justifyContent = 'center';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.style.background = '#ffebee';
            contentDiv.style.color = '#c62828';
            contentDiv.textContent = `❌ 错误: ${error}`;
            
            messageDiv.appendChild(contentDiv);
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        // =========================
        // Base64 转 Blob
        // =========================
        function base64ToBlob(base64, mimeType) {
            const byteCharacters = atob(base64);
            const byteNumbers = new Array(byteCharacters.length);
            
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            
            const byteArray = new Uint8Array(byteNumbers);
            return new Blob([byteArray], { type: mimeType });
        }

        // =========================
        // 控制输入
        // =========================
        function disableInput() {
            messageInput.disabled = true;
            sendBtn.disabled = true;
        }

        function enableInput() {
            messageInput.disabled = false;
            sendBtn.disabled = false;
            messageInput.focus();
        }

        // =========================
        // 回车发送
        // =========================
        messageInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        });

        // =========================
        // 初始化
        // =========================
        connectWebSocket();
    </script>
</body>
</html>
"""

# =========================
# 路由：主页
# =========================
@app.get("/")
async def get_root():
    return HTMLResponse(content=HTML_CONTENT)

# =========================
# WebSocket：处理对话
# =========================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global conversation_history
    
    await websocket.accept()
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "message":
                user_message = message_data.get("content", "").strip()
                
                if not user_message:
                    continue

                # 添加用户消息到历史（LongCat API 特殊要求）
                conversation_history.append({
                    "role": "user",
                    "content": [{"type": "text", "text": user_message}]
                })

                message_id = f"msg-{len(conversation_history)}"
                assistant_reply = ""

                try:
                    # 请求 API
                    stream = client.chat.completions.create(
                        model="LongCat-Flash-Omni-2603",
                        messages=conversation_history,
                        stream=True,
                        extra_body={
                            "output_modalities": ["text", "audio"],
                            "audio": {
                                "format": "pcm",
                                "sample_rate": 24000
                            }
                        }
                    )

                    # 流式处理
                    for chunk in stream:
                        delta = chunk.choices[0].delta

                        # 处理文本
                        if hasattr(delta, "content") and delta.content:
                            await websocket.send_json({
                                "type": "text",
                                "content": delta.content,
                                "message_id": message_id
                            })
                            assistant_reply += delta.content

                        # 处理音频
                        if hasattr(delta, "audio") and delta.audio:
                            audio_data = delta.audio

                            try:
                                if isinstance(audio_data, str):
                                    audio_bytes = base64.b64decode(audio_data)
                                elif hasattr(audio_data, "data") and audio_data.data:
                                    audio_bytes = base64.b64decode(audio_data.data)
                                else:
                                    continue

                                # 编码为 Base64 发送到前端
                                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                await websocket.send_json({
                                    "type": "audio",
                                    "audio_data": audio_base64,
                                    "message_id": message_id
                                })

                            except Exception as e:
                                print(f"音频处理错误: {e}")

                    # 添加 AI 回复到历史（LongCat API 特殊要求）
                    conversation_history.append({
                        "role": "user",
                        "content": [{"type": "text", "text": assistant_reply}]
                    })

                    # 发送完成信号
                    await websocket.send_json({
                        "type": "done",
                        "message_id": message_id
                    })

                except Exception as e:
                    print(f"API 请求错误: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

    except Exception as e:
        print(f"WebSocket 错误: {e}")
    finally:
        await websocket.close()

# =========================
# 启动服务
# =========================
if __name__ == "__main__":
    import uvicorn
    print("启动服务... http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
