import cv2
import time
import logging

logger = logging.getLogger(__name__)

class VideoCapture:
    def __init__(self, camera_index=0, target_fps=15):  # tăng mặc định lên 15
        self.camera_index = camera_index
        self.target_fps = target_fps
        self.cap = None
        self.frame_interval = 1.0 / target_fps
        self.last_frame_time = 0

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        # Ép bộ đệm bằng 1 để tránh kẹt frame cũ (chống delay từ phần cứng)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open webcam at index {self.camera_index}")
        
        # Đọc FPS thực tế của webcam (nếu có)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if actual_fps < self.target_fps and actual_fps > 0:
            logger.info(f"Webcam chỉ hỗ trợ {actual_fps:.2f} FPS, điều chỉnh target xuống {int(actual_fps)}")
            self.target_fps = int(actual_fps)
                
        self.frame_interval = 1.0 / self.target_fps
        logger.info(f"Webcam started at index {self.camera_index} with target FPS: {self.target_fps}")

    def read_frame(self):
        """Reads a frame honoring the target FPS."""
        if self.cap is None or not self.cap.isOpened():
            return None

        current_time = time.time()
        elapsed = current_time - self.last_frame_time

        if elapsed < self.frame_interval:
            # Không sleep chặn thread, trả về None để vòng lặp async tự yield
            return None
            
        ret, frame = self.cap.read()
        self.last_frame_time = time.time()

        if not ret:
            return None
            
        # KHÔNG RESIZE - giữ nguyên chất lượng cao
        return frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
            logger.info("Webcam released.")