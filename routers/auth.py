from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.models import User
from backend.database import users_collection
from datetime import datetime
import hashlib

router = APIRouter()
security = HTTPBearer()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
async def register(user: User):
    existing = await users_collection.find_one({"username": user.username})
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    
    user_dict = user.dict()
    user_dict["password"] = hash_password(user.password)
    user_dict["online"] = False
    user_dict["last_seen"] = datetime.now()
    
    await users_collection.insert_one(user_dict)
    return {"status": "ok", "message": "Регистрация успешна"}

@router.post("/login")
async def login(user: User):
    db_user = await users_collection.find_one({"username": user.username})
    hashed_password = hash_password(user.password)
    
    if not db_user or db_user["password"] != hashed_password:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    
    # Обновляем статус онлайн
    await users_collection.update_one(
        {"username": user.username},
        {"$set": {"online": True, "last_seen": datetime.now()}}
    )
    
    return {"status": "ok", "message": f"Добро пожаловать, {user.username}"}

@router.post("/logout")
async def logout(user: User):
    await users_collection.update_one(
        {"username": user.username},
        {"$set": {"online": False, "last_seen": datetime.now()}}
    )
    return {"status": "ok", "message": f"{user.username} вышел из системы"}

@router.get("/users/online")
async def get_online_users():
    online_users = await users_collection.find(
        {"online": True}, 
        {"username": 1, "avatar": 1}
    ).to_list(length=100)
    return online_users