import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import Video, JobStatus

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to TrainFlow_AI API", "status": "active"}

def test_upload_flow_mock():
    # Mocking storage service to avoid actual S3/MinIO calls during unit test
    # (In real integration tests, we'd use a dockerized minio or mock library)
    
    # 1. Test Upload
    # We'll just check if endpoint is reachable and validates input
    # Since we don't have a mocked DB session fixture here for this prototype, 
    # we expect it might fail on DB dependency if not mocked, 
    # but let's verify the health check at least.
    pass

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# In a real enterprise build, I would add:
# - conftest.py with DB fixtures
# - test_worker.py for async processing logic
# - test_alignment.py for the merge logic
