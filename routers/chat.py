from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from backend.database import messages_collection, users_collection, media_collection
from backend.models import Message, MessageType
from datetime import datetime
import json
import os
import uuid
import asyncio
from typing import Dict, List

router = APIRouter()

# Хранилище подключений
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.call_rooms: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_personal_message(self, message: str, username: str):
        if username in self.active_connections:
            await self.active_connections[username].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    async def send_json(self, data: dict, username: str):
        if username in self.active_connections:
            await self.active_connections[username].send_json(data)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections.values():
            await connection.send_json(data)

manager = ConnectionManager()

# Папка для медиафайлов
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

@router.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    
    # Отправляем историю сообщений
    recent_messages = await messages_collection.find().sort("timestamp", -1).limit(50).to_list(length=50)
    for msg in reversed(recent_messages):
        await manager.send_json(msg, username)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "call_offer":
                # Обработка предложения звонка
                await handle_call_offer(message_data, username)
            elif message_data.get("type") == "call_answer":
                # Обработка ответа на звонок
                await handle_call_answer(message_data, username)
            elif message_data.get("type") == "ice_candidate":
                # Обработка ICE кандидатов WebRTC
                await handle_ice_candidate(message_data, username)
            else:
                # Обычное текстовое сообщение
                message = Message(
                    sender=username,
                    text=message_data.get("text"),
                    message_type=MessageType.TEXT,
                    timestamp=datetime.now()
                )
                await messages_collection.insert_one(message.dict())
                await manager.broadcast_json(message.dict())
                
    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.broadcast_json({
            "type": "user_offline",
            "username": username
        })

async def handle_call_offer(data: dict, username: str):
    target_user = data.get("target_user")
    offer = data.get("offer")
    
    call_id = str(uuid.uuid4())
    manager.call_rooms[call_id] = {
        "caller": username,
        "callee": target_user,
        "offer": offer
    }
    
    # Отправляем предложение звонка целевому пользователю
    await manager.send_json({
        "type": "call_offer",
        "call_id": call_id,
        "caller": username,
        "offer": offer
    }, target_user)

async def handle_call_answer(data: dict, username: str):
    call_id = data.get("call_id")
    answer = data.get("answer")
    
    if call_id in manager.call_rooms:
        caller = manager.call_rooms[call_id]["caller"]
        await manager.send_json({
            "type": "call_answer",
            "call_id": call_id,
            "answer": answer
        }, caller)

async def handle_ice_candidate(data: dict, username: str):
    target_user = data.get("target_user")
    candidate = data.get("candidate")
    
    await manager.send_json({
        "type": "ice_candidate",
        "candidate": candidate
    }, target_user)

@router.post("/upload/media")
async def upload_media(file: UploadFile = File(...), username: str = Form(...)):
    file_extension = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(MEDIA_DIR, filename)
    
    # Сохраняем файл
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Определяем тип сообщения
    if file.content_type.startswith('image/'):
        message_type = MessageType.IMAGE
    elif file.content_type.startswith('video/'):
        message_type = MessageType.VIDEO
    elif file.content_type.startswith('audio/'):
        message_type = MessageType.VOICE
    else:
        message_type = MessageType.FILE
    
    # Сохраняем в базу данных
    message = Message(
        sender=username,
        text=file.filename,
        message_type=message_type,
        media_url=f"/media/{filename}",
        file_size=len(content),
        timestamp=datetime.now()
    )
    
    await messages_collection.insert_one(message.dict())
    await manager.broadcast_json(message.dict())
    
    return {"status": "ok", "filename": filename}