from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"
    FILE = "file"
    CALL = "call"

class User(BaseModel):
    username: str
    password: str
    online: bool = False
    last_seen: Optional[datetime] = None
    avatar: Optional[str] = None

class Message(BaseModel):
    sender: str
    text: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    media_url: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None  # для голосовых и видео
    timestamp: datetime = datetime.now()
    read_by: List[str] = []
    call_data: Optional[Dict[str, Any]] = None  # данные о звонке