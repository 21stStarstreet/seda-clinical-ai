from fastapi.testclient import TestClient
from api.main import app
import json

client = TestClient(app)

# Login to get token
response = client.post("/token", data={"username": "doktor", "password": "password"})
token = response.json()["access_token"]

# Fetch the log
res = client.get("/audit/logs/24", headers={"Authorization": f"Bearer {token}"})
print(res.status_code)
print(json.dumps(res.json(), indent=2))
