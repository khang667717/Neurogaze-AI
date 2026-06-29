# test_backend.py
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from backend.main import app
    from backend.database import Base, get_db
    from backend.config import API_TOKEN
except ImportError:
    from main import app
    from database import Base, get_db
    from config import API_TOKEN

# Setup test DB
TEST_DATABASE_URL = "sqlite:///./test_srvas.db"
engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Recreate tables for tests
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    def remove_test_db():
        if os.path.exists("test_srvas.db"):
            try:
                os.remove("test_srvas.db")
            except Exception:
                pass
    request.addfinalizer(remove_test_db)


def test_receive_event():
    response = client.post("/api/events", 
        json={
            "event_id": "123",
            "session_id": "test_session",
            "event_code": "PERSON_DETECTED",
            "timestamp": 123456.0,
            "confidence": 0.9,
            "payload": {}
        },
        headers={"X-API-Key": API_TOKEN}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_session_crud():
    # Create
    response = client.post("/api/sessions?session_id=test_session_1")
    assert response.status_code == 200
    
    # Get
    response = client.get("/api/sessions/test_session_1")
    assert response.status_code == 200
    assert response.json()["id"] == "test_session_1"
    
    # Not found
    response = client.get("/api/sessions/invalid_session")
    assert response.status_code == 404

def test_websocket():
    with client.websocket_connect(f"/ws/dashboard?token={API_TOKEN}") as websocket:
        # Tạm thời chỉ test khả năng kết nối thành công (không crash)
        assert websocket is not None

@pytest.mark.anyio
async def test_aggregator_logic(monkeypatch):
    import datetime
    import uuid
    try:
        from backend.aggregator import Aggregator
    except ImportError:
        from aggregator import Aggregator

    class MockWebsocketManager:
        async def broadcast(self, data):
            pass

    # Mock SessionLocal để không ghi vào file sqlite thật
    class MockSession:
        def add(self, *args): pass
        def commit(self): pass
        def close(self): pass
        def rollback(self): pass
        
    try:
        import backend.aggregator as agg_module
    except ImportError:
        import aggregator as agg_module
        
    monkeypatch.setattr(agg_module, "SessionLocal", lambda: MockSession())

    agg = Aggregator(MockWebsocketManager())
    
    # Kịch bản 1: 3 PERSON_DETECTED, 1 ATTENTION_DROP, 1 IDLE, 1 NO_PERSON
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "PERSON_DETECTED", "session_id": "s1"})
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "PERSON_DETECTED", "session_id": "s1"})
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "PERSON_DETECTED", "session_id": "s1"}) # 3.0
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "ATTENTION_DROP", "session_id": "s1"}) # 0.5
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "IDLE_DETECTED", "session_id": "s1"}) # 0.7
    agg.add_event({"event_id": str(uuid.uuid4()), "event_code": "NO_PERSON", "session_id": "s1"}) # 0.0
    # Total = 6, Score = 4.2. 4.2 / 6 * 100 = 70.0%
    
    # Ta phải lấy ra data broadcast để test
    broadcasted_data = []
    async def mock_broadcast(data):
        broadcasted_data.append(data)
    agg.websocket_manager.broadcast = mock_broadcast
    
    assert len(agg.buffer) == 6
    await agg.process_and_save()
    assert len(agg.buffer) == 0
    assert len(broadcasted_data) == 1
    assert broadcasted_data[0]["focus_score"] == 70.0
