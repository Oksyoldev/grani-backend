from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pymongo import MongoClient
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("Нет строки подключения к MongoDB! Проверь .env файл.")

# Async client for FastAPI
async_client = AsyncIOMotorClient(MONGO_URI)
async_db = async_client["grani_db"]

# Sync client for setup
sync_client = MongoClient(MONGO_URI)
sync_db = sync_client["grani_db"]

# Collections
users_collection = async_db["users"]
contacts_collection = async_db["contacts"] 
messages_collection = async_db["messages"]
contact_requests_collection = async_db["contact_requests"]

def setup_database():
    """Create indexes and initial data"""
    # Create indexes
    users_collection_sync = sync_db["users"]
    users_collection_sync.create_index("username", unique=True)
    contacts_collection_sync = sync_db["contacts"]
    contacts_collection_sync.create_index("user_id")
    messages_collection_sync = sync_db["messages"]
    messages_collection_sync.create_index([("from_user", 1), ("to_user", 1)])
    
    print("✅ Database setup complete")

# Run setup
if __name__ == "__main__":
    setup_database()