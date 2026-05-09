from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import base64
import json
import struct
import io
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
# PCM 转 WAV 函数
# =========================
def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """将 PCM 字节转换为 WAV 格式"""
    
    # WAV 文件头参数
    num_samples = len(pcm_data) // sample_width
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    
    # 创建 WAV 文件头
    wav_buffer = io.BytesIO()
    
    # RIFF chunk descriptor
    wav_buffer.write(b'RIFF')
    wav_buffer.write(struct.pack('<I', 36 + len(pcm_data)))  # chunk size
    wav_buffer.write(b'WAVE')
    
    # fmt sub-chunk
    wav_buffer.write(b'fmt ')
    wav_buffer.write(struct.pack('<I', 16))  # subchunk1 size
    wav_buffer.write(struct.pack('<H', 1))   # audio format (1 = PCM)
    wav_buffer.write(struct.pack('<H', channels))  # num channels
    wav_buffer.write(struct.pack('<I', sample_rate))  # sample rate
    wav_buffer.write(struct.pack('<I', byte_rate))  # byte rate
    wav_buffer.write(struct.pack('<H', block_align))  # block align
    wav_buffer.write(struct.pack('<H', sample_width * 8))  # bits per sample
    
    # data sub-chunk
    wav_buffer.write(b'data')
    wav_buffer.write(struct.pack('<I', len(pcm_data)))
    wav_buffer.write(pcm_data)
    
    return wav_buffer.getvalue()

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

        .audio-container {
            margin-top: 10px;
            display: flex;
            gap: 10px;
            align-items: center;
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

        .debug-info {
            font-size: 12px;
            color: #999;
            margin-top: 5px;
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
                console.log('✅ WebSocket 已连接');
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                console.log('📨 收到消息:', data.type);

                if (data.type === 'text') {
                    addOrUpdateMessage(data.content, 'assistant', data.message_id);
                } else if (data.type === 'audio') {
                    console.log('🔊 添加音频:', data.message_id);
                    addAudioToMessage(data.message_id, data.audio_data);
                } else if (data.type === 'done') {
                    console.log('✅ 对话完成');
                    enableInput();
                } else if (data.type === 'error') {
                    addErrorMessage(data.error);
                    enableInput();
                }
            };

            ws.onerror = function(error) {
                console.error('❌ WebSocket 错误:', error);
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
                // 检查是否已有音频容器
                let audioContainer = messageElement.querySelector('.audio-container');
                if (!audioContainer) {
                    audioContainer = document.createElement('div');
                    audioContainer.className = 'audio-container';
                    messageElement.appendChild(audioContainer);
                }

                try {
                    // 转换 Base64 为 Blob
                    const byteCharacters = atob(audioBase64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);

                    // 使用 WAV 格式
                    const audioBlob = new Blob([byteArray], { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);

                    // 创建音频元素
                    const audio = document.createElement('audio');
                    audio.controls = true;
                    audio.autoplay = true;
                    audio.style.width = '100%';
                    audio.style.maxWidth = '300px';
                    audio.src = audioUrl;
                    
                    audioContainer.appendChild(audio);
                    console.log('✅ 音频已添加并自动播放');

                } catch (e) {
                    console.error('❌ 音频处理失败:', e);
                    const errorDiv = document.createElement('div');
                    errorDiv.style.color = 'red';
                    errorDiv.textContent = '❌ 音频加载失败';
                    audioContainer.appendChild(errorDiv);
                }
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
                audio_chunks = []

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

                    print(f"[{message_id}] 开始流式处理...")

                    # 流式处理
                    for chunk in stream:
                        delta = chunk.choices[0].delta

                        # 处理文本
                        if hasattr(delta, "content") and delta.content:
                            print(f"[{message_id}] 收到文本: {delta.content}")
                            await websocket.send_json({
                                "type": "text",
                                "content": delta.content,
                                "message_id": message_id
                            })
                            assistant_reply += delta.content

                        # 处理音频
                        if hasattr(delta, "audio") and delta.audio:
                            audio_data = delta.audio
                            print(f"[{message_id}] 收到音频数据")

                            try:
                                # 尝试不同的音频数据格式
                                audio_bytes = None
                                
                                if isinstance(audio_data, str):
                                    # 直接 Base64 字符串
                                    audio_bytes = base64.b64decode(audio_data)
                                    print(f"[{message_id}] 直接 Base64 字符串: {len(audio_bytes)} bytes")
                                    
                                elif hasattr(audio_data, "data"):
                                    # 对象中的 data 属性
                                    if isinstance(audio_data.data, str):
                                        audio_bytes = base64.b64decode(audio_data.data)
                                    else:
                                        audio_bytes = audio_data.data
                                    print(f"[{message_id}] 对象数据: {len(audio_bytes)} bytes")
                                    
                                elif isinstance(audio_data, bytes):
                                    # 直接字节
                                    audio_bytes = audio_data
                                    print(f"[{message_id}] 直接字节: {len(audio_bytes)} bytes")

                                if audio_bytes:
                                    # 收集所有音频块
                                    audio_chunks.append(audio_bytes)

                            except Exception as e:
                                print(f"[{message_id}] 音频处理错误: {e}")
                                import traceback
                                traceback.print_exc()

                    # 流式处理完成，发送完整的音频
                    if audio_chunks:
                        print(f"[{message_id}] 收集 {len(audio_chunks)} 块音频")
                        complete_audio = b''.join(audio_chunks)
                        print(f"[{message_id}] 完整音频大小: {len(complete_audio)} bytes")
                        
                        # ⭐ 转换 PCM 为 WAV
                        wav_data = pcm_to_wav(complete_audio, sample_rate=24000, channels=1, sample_width=2)
                        audio_base64 = base64.b64encode(wav_data).decode('utf-8')
                        
                        await websocket.send_json({
                            "type": "audio",
                            "audio_data": audio_base64,
                            "message_id": message_id
                        })
                        print(f"[{message_id}] WAV 音频已发送: {len(audio_base64)} chars")
                    else:
                        print(f"[{message_id}] 没有收到音频数据")

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
                    print(f"[{message_id}] 完成")

                except Exception as e:
                    print(f"[{message_id}] API 请求错误: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

    except Exception as e:
        print(f"WebSocket 错误: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

# =========================
# 启动服务
# =========================
if __name__ == "__main__":
    import uvicorn
    print("启动服务... http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
