import time
import uuid
import logging
import cv2
import asyncio
import aiohttp
import os
import websockets
from capture import VideoCapture
from detector import BehaviorDetector
from event_generator import EventGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration via environment variables
TARGET_FPS = int(os.getenv("TARGET_FPS", "30")) # Giảm FPS xuống 15 để tiết kiệm CPU/Băng thông
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "3"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "1.0"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))
FRAME_SKIP = int(os.getenv("FRAME_SKIP", "1")) # Mặc định stream 15 FPS (giữ nguyên frame) để trải nghiệm mượt mà
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85")) # Hạ nhẹ quality xuống 70

# Auth Token
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.config import API_TOKEN

BACKEND_EVENT_URL = "http://localhost:8000/api/events"
BACKEND_WS_VIDEO_URL = f"ws://localhost:8000/ws/cv_video?token={API_TOKEN}"

async def http_event_worker(name, queue, session):
    """Worker task that reads events from the queue and sends HTTP POSTs. With retry logic."""
    MAX_RETRIES = 3
    while True:
        item = await queue.get()
        # Đảm bảo tương thích ngược nếu item vẫn là list (vài event còn kẹt trong queue)
        if isinstance(item, list):
            events = item
            retries = 0
        else:
            events = item.get("events", [])
            retries = item.get("retries", 0)
            
        success = False
        try:
            async with session.post(
                BACKEND_EVENT_URL,
                json=events,
                headers={"X-API-Key": API_TOKEN},
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            ) as response:
                if response.status == 200:
                    logger.debug(f"Worker {name}: {len(events)} events sent successfully.")
                    success = True
                else:
                    logger.warning(f"Worker {name}: Failed to send events (Status: {response.status})")
        except Exception as e:
            logger.error(f"Worker {name}: Connection error: {e}")
        finally:
            if not success:
                if retries < MAX_RETRIES:
                    logger.info(f"Worker {name}: Re-queueing {len(events)} failed events (Attempt {retries+1}/{MAX_RETRIES}).")
                    await queue.put({"events": events, "retries": retries + 1})
                    await asyncio.sleep(1) # Backoff before processing next
                else:
                    logger.error(f"Worker {name}: Dropping {len(events)} events after {MAX_RETRIES} failed attempts.")
            queue.task_done()

async def websocket_video_worker(frame_queue):
    """Worker task that maintains a WebSocket connection and streams frames."""
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(BACKEND_WS_VIDEO_URL) as ws:
                logger.info("Connected to Backend Video WebSocket")
                backoff = 1.0
                while True:
                    jpeg_bytes = await frame_queue.get()
                    try:
                        await ws.send(jpeg_bytes)
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Video WebSocket closed. Reconnecting...")
                        break
                    finally:
                        frame_queue.task_done()
        except Exception as e:
            logger.error(f"Video WS Error: {e}. Retrying in {backoff} seconds...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)

async def main_async():
    session_id = str(uuid.uuid4())
    logger.info(f"Starting CV Module. Session ID: {session_id}")
    logger.info(f"Config: FPS={TARGET_FPS}, SKIP={FRAME_SKIP}, QUALITY={JPEG_QUALITY}, WORKERS={MAX_WORKERS}")
    
    cap = VideoCapture(target_fps=TARGET_FPS)
    detector = BehaviorDetector()
    generator = EventGenerator(session_id)
    
    try:
        cap.start()
    except RuntimeError as e:
        logger.error(f"Failed to start webcam: {e}")
        return
        
    event_queue = asyncio.Queue()
    frame_queue = asyncio.Queue(maxsize=30) # Prevent memory bloat if network is slow
    
    async with aiohttp.ClientSession() as session:
        workers = []
        for i in range(MAX_WORKERS):
            workers.append(asyncio.create_task(http_event_worker(f"W-{i+1}", event_queue, session)))
            
        video_worker = asyncio.create_task(websocket_video_worker(frame_queue))
        workers.append(video_worker)
            
        event_batch = []
        frame_counter = 0
        
        try:
            while True:
                frame = await asyncio.to_thread(cap.read_frame)
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue
                    
                current_time = time.time()
                frame_counter += 1
                
                # 1. Detection
                detection_result = await asyncio.to_thread(detector.detect, frame, current_time)
                
                # 2. Generate events
                events = generator.generate_events(detection_result, current_time)
                event_batch.extend(events)
                
                # 3. Queue frames via WebSocket (dropping oldest if full)
                if frame_counter % max(1, FRAME_SKIP) == 0:
                    encode_param = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    _, encoded_img = await asyncio.to_thread(cv2.imencode, '.jpg', frame, encode_param)
                    jpeg_bytes = encoded_img.tobytes()
                    try:
                        frame_queue.put_nowait(jpeg_bytes)
                    except asyncio.QueueFull:
                        # Drop oldest frame to keep realtime
                        frame_queue.get_nowait()
                        frame_queue.task_done()
                        frame_queue.put_nowait(jpeg_bytes)
                
                # 4. Flush events batch
                flush_now = False
                if len(event_batch) >= BATCH_SIZE:
                    flush_now = True
                else:
                    urgent_events = {"ATTENTION_DROP", "NO_PERSON"}
                    if any(e["event_code"] in urgent_events for e in events):
                        flush_now = True
                            
                if flush_now and event_batch:
                    await event_queue.put({"events": list(event_batch), "retries": 0})
                    event_batch.clear()
                
                await asyncio.sleep(0)
                
        except asyncio.CancelledError:
            logger.info("Main async loop cancelled.")
        finally:
            cap.release()
            detector.release()
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("CV Module stopped by user.")