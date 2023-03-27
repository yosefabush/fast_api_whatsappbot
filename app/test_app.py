import os
from app import app
from fastapi import status
from fastapi.testclient import TestClient
# TOKEN = os.getenv('TOKEN', default=None)
TOKEN = os.environ["TOKEN"]
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]

client = TestClient(app=app)


def test_root():
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"Hello": "FastAPI"}
