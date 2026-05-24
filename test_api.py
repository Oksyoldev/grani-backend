import requests
import json

def test_api():
    print("🧪 Testing Grani API...")
    
    # Тест регистрации
    print("1. Testing registration...")
    try:
        response = requests.post(
            "http://localhost:8000/register",
            json={"username": "testuser", "password": "testpass"},
            headers={"Content-Type": "application/json"}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Тест входа
    print("\n2. Testing login...")
    try:
        response = requests.post(
            "http://localhost:8000/login", 
            json={"username": "testuser", "password": "testpass"},
            headers={"Content-Type": "application/json"}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Тест получения пользователей
    print("\n3. Testing users list...")
    try:
        response = requests.get("http://localhost:8000/users")
        print(f"   Status: {response.status_code}")
        print(f"   Users: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_api()