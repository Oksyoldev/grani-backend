from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("Нет строки подключения к MongoDB! Проверь .env файл.")

# Синхронный клиент
client = MongoClient(MONGO_URI)
db = client["grani_db"]

# Коллекции
users_collection = db["users"]
contacts_collection = db["contacts"]
messages_collection = db["messages"]
contact_requests_collection = db["contact_requests"]

def setup_database():
    """Create indexes"""
    users_collection.create_index("username", unique=True)
    contacts_collection.create_index("user_id")
    messages_collection.create_index([("from_user", 1), ("to_user", 1)])
    print("✅ Database setup complete")

if __name__ == "__main__":
    setup_database()