# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Response, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DBSession
from typing import List, Set, Optional
import asyncio
import os
import logging

from .database import engine, Base, get_db
from .models import Session
from .aggregator import Aggregator

# Cấu hình logging
logger = logging.getLogger(__name__)

from .config import API_TOKEN

def verify_token(x_api_key: Optional[str] = Header(None)):
    """Xác thực API token từ header X-API-Key"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

async def verify_ws_token(websocket: WebSocket, token: str):
    """Xác thực WebSocket token từ query parameter"""
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return False
    if token != API_TOKEN:
        await websocket.close(code=1008, reason="Invalid token")
        return False
    return True

# Tạo bảng DB
Base.metadata.create_all(bind=engine)

# ⚙️ Cấu hình Rate Limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="SRVAS Personal MVP 10/10")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={"detail": "Too many requests. Try again later."}
))

# Security: CORS configuration from environment
# Default to localhost for development, restrict in production
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]
logger.info(f"CORS enabled for origins: {CORS_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    """Quản lý kết nối Dashboard Events (JSON)"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Event WS Error: {e}")

class VideoStreamingManager:
    """In-memory Pub/Sub cho luồng Video MJPEG bằng WebSocket"""
    def __init__(self):
        self.subscribers: Set[WebSocket] = set()

    async def connect_subscriber(self, websocket: WebSocket):
        await websocket.accept()
        self.subscribers.add(websocket)
        logger.info(f"Dashboard Video Subscriber connected. Total: {len(self.subscribers)}")

    def disconnect_subscriber(self, websocket: WebSocket):
        if websocket in self.subscribers:
            self.subscribers.remove(websocket)
            logger.info(f"Dashboard Video Subscriber disconnected. Total: {len(self.subscribers)}")

    async def broadcast_frame(self, frame_bytes: bytes):
        if not self.subscribers:
            return
            
        disconnected = set()
        
        async def send_to_sub(sub):
            try:
                await sub.send_bytes(frame_bytes)
            except Exception as e:
                logger.error(f"Video WS Error: {e}")
                disconnected.add(sub)
                
        # Non-blocking concurrent broadcast
        await asyncio.gather(*(send_to_sub(sub) for sub in self.subscribers))
        
        # Cleanup failed connections
        for sub in disconnected:
            self.subscribers.remove(sub)

manager = ConnectionManager()
video_manager = VideoStreamingManager()
aggregator = Aggregator(manager)

@app.on_event("startup")
async def startup_event():
    # Khởi động background task của aggregator
    asyncio.create_task(aggregator.run())

# Health Check Endpoint (cho load balancers, Kubernetes, monitoring)
@app.get("/health")
async def health_check():
    """Health check endpoint - returns OK if service is running"""
    return {
        "status": "ok",
        "service": "SRVAS Personal MVP",
        "version": "1.0.0"
    }

# API Nhận Event (CV Module gửi lên bằng Token)
@app.post("/api/events")
async def receive_events(request: Request, token: str = Depends(verify_token)):
    # Nhận một mảng hoặc một object event
    data = await request.json()
    if isinstance(data, list):
        for event in data:
            aggregator.add_event(event)
    else:
        aggregator.add_event(data)
    return {"status": "ok"}

# API Test Rate Limiting (riêng cho test, không dùng trong production)
@app.post("/api/test_rate_limit")
@limiter.limit("100/minute")
async def test_rate_limit(request: Request, token: str = Depends(verify_token)):
    """Test endpoint với rate limiting 100/minute"""
    return {"status": "ok", "message": "Rate limit test"}

# --- WebSockets ---
@app.websocket("/ws/cv_video")
async def websocket_cv_video(websocket: WebSocket, token: str = None):
    """CV Module đẩy frame nhị phân (JPEG) liên tục qua connection này"""
    if not await verify_ws_token(websocket, token):
        return
    await websocket.accept()
    logger.info("CV Video Publisher connected.")
    try:
        while True:
            # Nhận frame nhị phân từ CV Module
            frame_bytes = await websocket.receive_bytes()
            # Broadcast ngay lập tức cho các Dashboard Subscribers
            await video_manager.broadcast_frame(frame_bytes)
    except WebSocketDisconnect:
        logger.info("CV Video Publisher disconnected.")
    except Exception as e:
        logger.error(f"CV Video WS Error: {e}")

@app.websocket("/ws/video_feed")
async def websocket_dashboard_video(websocket: WebSocket, token: str = None):
    """Dashboard lắng nghe frame nhị phân để render"""
    if not await verify_ws_token(websocket, token):
        return
    await video_manager.connect_subscriber(websocket)
    try:
        while True:
            # Giữ kết nối mở, client không cần gửi gì
            await websocket.receive_text()
    except WebSocketDisconnect:
        video_manager.disconnect_subscriber(websocket)
    except Exception as e:
        logger.error(f"Dashboard Video Sub Error: {e}")
        video_manager.disconnect_subscriber(websocket)

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str = None):
    """Dashboard nhận các sự kiện thông số (Focus Score, v.v.)"""
    if not await verify_ws_token(websocket, token):
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Dashboard Event WS Error: {e}")
        manager.disconnect(websocket)

# --- CRUD Sessions ---
@app.post("/api/sessions")
def create_session(session_id: str, db: DBSession = Depends(get_db)):
    db_sess = db.query(Session).filter(Session.id == session_id).first()
    if not db_sess:
        db_sess = Session(id=session_id)
        db.add(db_sess)
        db.commit()
    return {"status": "created", "id": session_id}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    db_sess = db.query(Session).filter(Session.id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_sess

@app.get("/api/dashboard")
def get_dashboard_init(db: DBSession = Depends(get_db)):
    # Trả về thông tin cơ bản khi mở dashboard
    return {"status": "running", "message": "Connect to /ws/dashboard for real-time updates"}

# Serve thư mục tĩnh nếu có
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")
if os.path.exists(DASHBOARD_DIR):
    app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
