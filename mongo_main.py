from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import json
import uuid
from database import users_collection, contacts_collection, messages_collection, contact_requests_collection, setup_database
from bson import ObjectId
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Grani Messenger API is running"}

# Модели данных
class User(BaseModel):
    username: str
    password: str

class ContactRequest(BaseModel):
    from_user: str
    to_user: str

class Message(BaseModel):
    from_user: str
    to_user: str
    text: str
    message_type: str = "text"
    timestamp: datetime = datetime.now()
    read: bool = False

active_connections = {}

# MongoDB helpers
def user_to_dict(user):
    return {
        "username": user["username"],
        "password": user["password"]
    }

# API Routes
@app.post("/register")
async def register(user: User):
    # Check if user exists
    existing_user = await users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    
    # Create user
    user_dict = user.dict()
    await users_collection.insert_one(user_dict)
    
    # Initialize contacts
    await contacts_collection.insert_one({
        "user_id": user.username,
        "contacts": []
    })
    
    return {"status": "ok", "message": "Регистрация успешна"}

@app.post("/login")
async def login(user: User):
    db_user = await users_collection.find_one({
        "username": user.username,
        "password": user.password
    })
    
    if not db_user:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    
    return {"status": "ok", "message": f"Добро пожаловать, {user.username}"}

@app.get("/users")
async def search_users(query: str = ""):
    if not query:
        return []
    
    # Search users (case insensitive)
    users_cursor = users_collection.find({
        "username": {"$regex": query, "$options": "i"}
    })
    
    users = await users_cursor.to_list(length=20)
    results = [user["username"] for user in users]
    
    return results

@app.post("/contacts/request")
async def send_contact_request(request: ContactRequest):
    # Check if target user exists
    target_user = await users_collection.find_one({"username": request.to_user})
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Check if request already exists
    existing_request = await contact_requests_collection.find_one({
        "from_user": request.from_user,
        "to_user": request.to_user,
        "status": "pending"
    })
    
    if existing_request:
        raise HTTPException(status_code=400, detail="Запрос уже отправлен")
    
    # Check if already contacts
    user_contacts = await contacts_collection.find_one({"user_id": request.from_user})
    if user_contacts and request.to_user in user_contacts.get("contacts", []):
        raise HTTPException(status_code=400, detail="Пользователь уже в контактах")
    
    # Create request
    await contact_requests_collection.insert_one({
        "from_user": request.from_user,
        "to_user": request.to_user,
        "status": "pending",
        "created_at": datetime.now()
    })
    
    # Notify recipient if online
    if request.to_user in active_connections:
        ws = active_connections[request.to_user]
        await ws.send_text(json.dumps({
            "type": "contact_request",
            "from_user": request.from_user,
            "request_id": str(ObjectId())
        }))
    
    return {"status": "ok", "message": "Запрос отправлен"}

@app.post("/contacts/request/cancel")
async def cancel_contact_request(request: ContactRequest):
    # Delete pending request
    result = await contact_requests_collection.delete_one({
        "from_user": request.from_user,
        "to_user": request.to_user,
        "status": "pending"
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    
    return {"status": "ok", "message": "Запрос отменен"}

@app.get("/contacts/requests/sent/{username}")
async def get_sent_requests(username: str):
    """Get requests sent by user"""
    requests_cursor = contact_requests_collection.find({
        "from_user": username,
        "status": "pending"
    })
    
    requests = await requests_cursor.to_list(length=50)
    return [{"to_user": req["to_user"]} for req in requests]

@app.post("/contacts/accept")
async def accept_contact_request(request: ContactRequest):
    # Find and update request
    contact_request = await contact_requests_collection.find_one({
        "from_user": request.from_user,
        "to_user": request.to_user,
        "status": "pending"
    })
    
    if not contact_request:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    
    # Update request status
    await contact_requests_collection.update_one(
        {"_id": contact_request["_id"]},
        {"$set": {"status": "accepted", "accepted_at": datetime.now()}}
    )
    
    # Add to contacts for both users
    await contacts_collection.update_one(
        {"user_id": request.to_user},
        {"$addToSet": {"contacts": request.from_user}},
        upsert=True
    )
    
    await contacts_collection.update_one(
        {"user_id": request.from_user},
        {"$addToSet": {"contacts": request.to_user}},
        upsert=True
    )
    
    return {"status": "ok", "message": "Контакт добавлен"}

@app.post("/contacts/remove")
async def remove_contact(request: ContactRequest):
    # Remove from both users' contacts
    await contacts_collection.update_one(
        {"user_id": request.from_user},
        {"$pull": {"contacts": request.to_user}}
    )
    
    await contacts_collection.update_one(
        {"user_id": request.to_user},
        {"$pull": {"contacts": request.from_user}}
    )
    
    return {"status": "ok", "message": "Контакт удален"}

@app.get("/contacts/{username}")
async def get_contacts(username: str):
    user_contacts = await contacts_collection.find_one({"user_id": username})
    if not user_contacts:
        return []
    
    contacts_with_info = []
    for contact_username in user_contacts.get("contacts", []):
        contact_info = {
            "username": contact_username,
            "online": contact_username in active_connections
        }
        contacts_with_info.append(contact_info)
    
    return contacts_with_info

@app.get("/contact-requests/{username}")
async def get_contact_requests(username: str):
    """Get incoming requests"""
    requests_cursor = contact_requests_collection.find({
        "to_user": username,
        "status": "pending"
    })
    
    requests = await requests_cursor.to_list(length=50)
    return [req["from_user"] for req in requests]

@app.get("/messages/{from_user}/{to_user}")
async def get_messages(from_user: str, to_user: str):
    messages_cursor = messages_collection.find({
        "$or": [
            {"from_user": from_user, "to_user": to_user},
            {"from_user": to_user, "to_user": from_user}
        ]
    }).sort("timestamp", 1)
    
    messages = await messages_cursor.to_list(length=100)
    
    # Convert ObjectId to string
    for msg in messages:
        msg["id"] = str(msg["_id"])
        del msg["_id"]
    
    return messages

@app.delete("/messages/{message_id}")
async def delete_message(message_id: str):
    try:
        result = await messages_collection.delete_one({"_id": ObjectId(message_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        return {"status": "ok", "message": "Сообщение удалено"}
    except:
        raise HTTPException(status_code=400, detail="Неверный ID сообщения")

@app.get("/create-test-users")
async def create_test_users():
    """Создает тестовых пользователей"""
    test_users = [
        {"username": "Алексей", "password": "123"},
        {"username": "Мария", "password": "123"},
        {"username": "Иван", "password": "123"},
        {"username": "Елена", "password": "123"}
    ]
    
    created = 0
    for user in test_users:
        existing = await users_collection.find_one({"username": user["username"]})
        if not existing:
            await users_collection.insert_one(user)
            await contacts_collection.insert_one({
                "user_id": user["username"],
                "contacts": []
            })
            created += 1
    
    return {"status": "ok", "message": f"Создано {created} тестовых пользователей"}

# WebSocket для реального времени
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections[username] = websocket
    
    try:
        # Send pending contact requests
        requests_cursor = contact_requests_collection.find({
            "to_user": username,
            "status": "pending"
        })
        requests = await requests_cursor.to_list(length=20)
        
        for request in requests:
            await websocket.send_text(json.dumps({
                "type": "contact_request",
                "from_user": request["from_user"]
            }))
        
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                # Save message to database
                new_message = {
                    "from_user": username,
                    "to_user": message_data["to_user"],
                    "text": message_data["text"],
                    "message_type": message_data.get("message_type", "text"),
                    "timestamp": datetime.now(),
                    "read": False
                }
                
                result = await messages_collection.insert_one(new_message)
                message_id = str(result.inserted_id)
                
                # Send to recipient if online
                if message_data["to_user"] in active_connections:
                    recipient_ws = active_connections[message_data["to_user"]]
                    await recipient_ws.send_text(json.dumps({
                        "type": "new_message",
                        "message": {
                            "id": message_id,
                            "from_user": username,
                            "text": message_data["text"],
                            "timestamp": new_message["timestamp"].isoformat()
                        }
                    }))
                
                # Confirm to sender
                await websocket.send_text(json.dumps({
                    "type": "message_sent",
                    "message_id": message_id
                }))
                
    except WebSocketDisconnect:
        if username in active_connections:
            del active_connections[username]

# Эндпоинты для Избранного
@app.post("/favorites/add")
async def add_to_favorites(message_data: dict):
    """Добавить сообщение в избранное"""
    favorite_message = {
        "user_id": message_data["user_id"],
        "from_user": message_data["from_user"],
        "text": message_data["text"],
        "message_type": message_data.get("message_type", "text"),
        "timestamp": datetime.now(),
        "is_favorite": True
    }
    
    result = await messages_collection.insert_one(favorite_message)
    return {"status": "ok", "message_id": str(result.inserted_id)}

@app.get("/favorites/{username}")
async def get_favorites(username: str):
    """Получить все избранные сообщения пользователя"""
    favorites_cursor = messages_collection.find({
        "user_id": username,
        "is_favorite": True
    }).sort("timestamp", -1)
    
    favorites = await favorites_cursor.to_list(length=100)
    
    # Convert ObjectId to string
    for fav in favorites:
        fav["id"] = str(fav["_id"])
        del fav["_id"]
    
    return favorites

@app.delete("/favorites/{message_id}")
async def remove_from_favorites(message_id: str):
    """Удалить сообщение из избранного"""
    try:
        result = await messages_collection.delete_one({"_id": ObjectId(message_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        return {"status": "ok", "message": "Удалено из избранного"}
    except:
        raise HTTPException(status_code=400, detail="Неверный ID сообщения")

@app.on_event("startup")
async def startup_event():
    setup_database()
    print("✅ Database initialized")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Grani Messenger with MongoDB Starting...")
    print("📡 API: http://localhost:8000")
    print("💾 MongoDB Atlas connected")
    uvicorn.run(app, host="0.0.0.0", port=8000)