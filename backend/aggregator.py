# aggregator.py
import asyncio
import datetime
from sqlalchemy.orm import Session as DBSession
from .database import SessionLocal
from .models import SessionAggregate
import logging

logger = logging.getLogger(__name__)

class Aggregator:
    """
    Aggregates events over a fixed time window to compute a focus score and active ratio.
    It collects real-time computer vision events into a buffer and periodically
    calculates statistics to save into the database and broadcast via WebSocket.
    """
    def __init__(self, websocket_manager):
        self.buffer = []
        self.websocket_manager = websocket_manager

    def add_event(self, event_data: dict):
        """
        Adds a new event dictionary to the internal buffer.
        """
        self.buffer.append(event_data)

    def _save_to_db(self, agg_data):
        """Chạy trong thread riêng để không block Event Loop. Trả về True nếu lưu thành công."""
        db: DBSession = SessionLocal()
        try:
            new_agg = SessionAggregate(
                session_id=agg_data["session_id"],
                focus_score=agg_data["focus_score"],
                active_ratio=agg_data["active_ratio"]
            )
            db.add(new_agg)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"DB Error: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    async def process_and_save(self):
        """
        Xử lý sự kiện theo từng session_id.
        Chỉ xóa event khỏi buffer nếu đã lưu DB thành công.
        """
        if not self.buffer:
            return

        # Tạo bản sao để không block buffer chính
        events_to_process = self.buffer.copy()
        
        # Nhóm theo session_id
        sessions = {}
        for e in events_to_process:
            sid = e.get("session_id", "unknown")
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(e)
            
        successful_event_ids = set()
        
        for sid, events in sessions.items():
            total = len(events)
            score_sum = 0.0
            active_count = 0
            
            for e in events:
                code = e['event_code']
                if code == 'PERSON_DETECTED':
                    score_sum += 1.0
                    active_count += 1
                elif code == 'ATTENTION_DROP':
                    score_sum += 0.5
                    active_count += 1
                elif code == 'IDLE_DETECTED':
                    score_sum += 0.7
                    active_count += 1
                elif code == 'NO_PERSON':
                    pass
                    
            focus_score = (score_sum / total) * 100.0 if total > 0 else 0.0
            active_ratio = (active_count / total) * 100.0 if total > 0 else 0.0
            
            agg_data = {
                "session_id": sid,
                "focus_score": focus_score,
                "active_ratio": active_ratio
            }
            
            # Ghi DB không block I/O
            success = await asyncio.to_thread(self._save_to_db, agg_data)
            
            if success:
                for e in events:
                    if 'event_id' in e:
                        successful_event_ids.add(e['event_id'])
                
                # Broadcast
                ws_data = {
                    "type": "aggregate",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "session_id": sid,
                    "focus_score": round(focus_score, 2),
                    "active_ratio": round(active_ratio, 2)
                }
                await self.websocket_manager.broadcast(ws_data)
                
        # Lọc bỏ các event đã xử lý thành công bằng UUID
        self.buffer = [e for e in self.buffer if e.get('event_id') not in successful_event_ids]

        # Bảo vệ tràn bộ nhớ (Memory Leak Protection) nếu DB chết liên tục
        MAX_BUFFER_SIZE = 500
        if len(self.buffer) > MAX_BUFFER_SIZE:
            overflow = len(self.buffer) - MAX_BUFFER_SIZE
            self.buffer = self.buffer[overflow:]
            logger.error(f"CRITICAL: DB unreachable. Dropped {overflow} oldest events")

    async def run(self):
        """Vòng lặp chạy ngầm mỗi 2 giây."""
        while True:
            await asyncio.sleep(2)
            await self.process_and_save()
