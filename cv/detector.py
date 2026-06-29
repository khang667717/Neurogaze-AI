import cv2
import numpy as np
import logging
import ssl

# Bypass SSL certificate verification on macOS Python
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_MEDIAPIPE = True
try:
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_face_detection = mp.solutions.face_detection
    mp_face_mesh = mp.solutions.face_mesh
except (ImportError, AttributeError) as e:
    logger.warning(f"MediaPipe not available ({e}). Falling back to motion-only.")
    USE_MEDIAPIPE = False

def non_max_suppression(boxes, scores=None, iou_threshold=0.3):
    if len(boxes) == 0:
        return []
    rects = np.array([(x, y, x+w, y+h) for (x, y, w, h) in boxes])
    x1, y1, x2, y2 = rects[:, 0], rects[:, 1], rects[:, 2], rects[:, 3]
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    if scores is None:
        scores = area
    else:
        scores = np.array(scores)
    idxs = np.argsort(scores)[::-1]
    pick = []
    while len(idxs) > 0:
        i = idxs[0]
        pick.append(i)
        if len(idxs) == 1:
            break
        xx1 = np.maximum(x1[i], x1[idxs[1:]])
        yy1 = np.maximum(y1[i], y1[idxs[1:]])
        xx2 = np.minimum(x2[i], x2[idxs[1:]])
        yy2 = np.minimum(y2[i], y2[idxs[1:]])
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        overlap = (w * h) / area[idxs[1:]]
        idxs = np.delete(idxs, np.concatenate(([0], np.where(overlap > iou_threshold)[0] + 1)))
    return [(rects[i][0], rects[i][1], rects[i][2]-rects[i][0], rects[i][3]-rects[i][1]) for i in pick]

class BehaviorDetector:
    def __init__(self, motion_threshold=10000, idle_seconds_threshold=3.0):
        self.motion_threshold = motion_threshold
        self.idle_seconds_threshold = idle_seconds_threshold
        self.last_gray_frame = None
        self.last_motion_time = None
        
        # State tracking per face index
        self.face_states = {}
        self.landmark_motion_threshold = 0.02
        self.use_mediapipe = USE_MEDIAPIPE
        self.ear_threshold = 0.21
        
        if self.use_mediapipe:
            self.mp_face_detection = mp_face_detection
            self.mp_face_mesh = mp_face_mesh
            self.face_detection = self.mp_face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5
            )
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=10,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.frame_count = 0

    def _is_valid_face_box(self, frame_gray, x, y, w, h):
        fh, fw = frame_gray.shape
        if w < 50 or h < 50 or w > fw*0.95 or h > fh*0.95:
            return False
        ratio = w / float(h)
        if ratio < 0.4 or ratio > 1.8:
            return False
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(fw, x + w), min(fh, y + h)
        if x2 <= x1 or y2 <= y1:
            return False
        roi = frame_gray[y1:y2, x1:x2]
        if np.mean(roi) > 245:
            return False
        return True

    def detect(self, frame, timestamp):
        self.frame_count += 1
        gray_for_filter = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        mesh_res = None
        face_results = []
        
        if self.use_mediapipe:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mesh_res = self.face_mesh.process(rgb)
            
            if mesh_res and mesh_res.multi_face_landmarks:
                h, w = frame.shape[:2]
                for idx, face_landmarks in enumerate(mesh_res.multi_face_landmarks):
                    landmarks = face_landmarks.landmark
                    
                    # Bounding Box Extraction from Landmarks
                    xs = [lm.x for lm in landmarks]
                    ys = [lm.y for lm in landmarks]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                    
                    bw = (xmax - xmin) * w
                    bh = (ymax - ymin) * h
                    pad_x = bw * 0.15
                    pad_y = bh * 0.15
                    
                    x_box = int(max(0, xmin * w - pad_x))
                    y_box = int(max(0, ymin * h - pad_y * 1.5))
                    w_box = int(min(w - x_box, bw + 2 * pad_x))
                    h_box = int(min(h - y_box, bh + 2 * pad_y))
                    
                    box = (x_box, y_box, w_box, h_box)
                    
                    # Ensure state memory exists for this face index
                    if idx not in self.face_states:
                        self.face_states[idx] = {
                            "closed_eyes_frames": 0, 
                            "last_landmarks": None, 
                            "last_landmark_motion_time": timestamp
                        }
                    
                    # Compute individual state
                    is_idle = self._detect_idle_mesh(landmarks, timestamp, idx)
                    attention_drop, drop_reason = self._check_attention_drop_mesh(landmarks, idx)
                    
                    face_results.append({
                        "box": box,
                        "is_idle": is_idle,
                        "attention_drop": attention_drop,
                        "drop_reason": drop_reason
                    })
        
        # Fallback if MediaPipe FaceMesh fails to find anyone
        if len(face_results) == 0:
            is_idle_global = self._detect_idle(frame, timestamp)
            all_boxes = []
            all_scores = []
            
            if self.use_mediapipe:
                self.face_detection.min_detection_confidence = 0.45
                results = self.face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if results and results.detections:
                    h, w = frame.shape[:2]
                    for det in results.detections:
                        score = det.score[0] if det.score else 0.0
                        if score > 0.4:
                            bbox = det.location_data.relative_bounding_box
                            bx = int(bbox.xmin * w)
                            by = int(bbox.ymin * h)
                            bwidth = int(bbox.width * w)
                            bheight = int(bbox.height * h)
                            if self._is_valid_face_box(gray_for_filter, bx, by, bwidth, bheight):
                                all_boxes.append((bx, by, bwidth, bheight))
                                all_scores.append(score)
            
            # Haar Cascade fallback if even face_detection fails
            if len(all_boxes) == 0:
                faces = self.face_cascade.detectMultiScale(
                    gray_for_filter, scaleFactor=1.1, minNeighbors=8, minSize=(60, 60)
                )
                for (bx, by, bw, bh) in faces:
                    if self._is_valid_face_box(gray_for_filter, bx, by, bw, bh):
                        all_boxes.append((bx, by, bw, bh))
                        all_scores.append(1.0)
            
            if len(all_boxes) > 1:
                all_boxes = non_max_suppression(all_boxes, all_scores, iou_threshold=0.3)
                
            for box in all_boxes:
                face_results.append({
                    "box": box,
                    "is_idle": is_idle_global,
                    "attention_drop": False,
                    "drop_reason": ""
                })

        # Process Results and Draw Individually
        face_events = []
        for face in face_results:
            if face["attention_drop"]:
                status_text = face["drop_reason"] if face["drop_reason"] else "ATTENTION DROP"
                color = (0, 0, 255)
                event_code = "ATTENTION_DROP"
            elif face["is_idle"]:
                status_text = "IDLE (NO MOTION)"
                color = (0, 255, 255)
                event_code = "IDLE_DETECTED"
            else:
                status_text = "FOCUSED"
                color = (0, 255, 0)
                event_code = "PERSON_DETECTED"
                
            face_events.append(event_code)
            
            x, y, bw, bh = face["box"]
            cv2.rectangle(frame, (x, y), (x+bw, y+bh), color, 2)
            
            label = f"Human ({status_text})"
            text_y = y - 5 if y - 5 > 20 else y + bh + 15
            cv2.putText(frame, label, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw empty room state
        if len(face_results) == 0:
            cv2.putText(frame, "STATUS: NO PERSON", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            # Motion check for empty room (optional, just to keep frame difference active)
            self._detect_idle(frame, timestamp)

        return {
            "face_events": face_events
        }

    def _detect_idle(self, frame, timestamp):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.last_gray_frame is None:
            self.last_gray_frame = gray
            self.last_motion_time = timestamp
            return False
        frame_delta = cv2.absdiff(self.last_gray_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        motion_score = np.sum(thresh) / 255
        if motion_score > self.motion_threshold:
            self.last_motion_time = timestamp
        else:
            if (timestamp - self.last_motion_time) > self.idle_seconds_threshold:
                return True
        self.last_gray_frame = gray
        return False

    def _detect_idle_mesh(self, landmarks, timestamp, face_idx):
        key_indices = [1, 234, 454]
        current = [(landmarks[idx].x, landmarks[idx].y) for idx in key_indices]
        
        state = self.face_states.get(face_idx)
        if not state: return False
        
        if state["last_landmarks"] is None:
            state["last_landmarks"] = current
            state["last_landmark_motion_time"] = timestamp
            return False
            
        max_dist = 0.0
        for i, (cx, cy) in enumerate(current):
            px, py = state["last_landmarks"][i]
            dist = ((cx-px)**2 + (cy-py)**2)**0.5
            if dist > max_dist:
                max_dist = dist
                
        if max_dist > self.landmark_motion_threshold:
            state["last_landmarks"] = current
            state["last_landmark_motion_time"] = timestamp
            return False
        else:
            if state["last_landmark_motion_time"] is None:
                state["last_landmark_motion_time"] = timestamp
            return (timestamp - state["last_landmark_motion_time"]) > self.idle_seconds_threshold

    def _calculate_ear(self, landmarks, eye_indices):
        p1 = np.array([landmarks[eye_indices[0]].x, landmarks[eye_indices[0]].y])
        p2 = np.array([landmarks[eye_indices[1]].x, landmarks[eye_indices[1]].y])
        p3 = np.array([landmarks[eye_indices[2]].x, landmarks[eye_indices[2]].y])
        p4 = np.array([landmarks[eye_indices[3]].x, landmarks[eye_indices[3]].y])
        p5 = np.array([landmarks[eye_indices[4]].x, landmarks[eye_indices[4]].y])
        p6 = np.array([landmarks[eye_indices[5]].x, landmarks[eye_indices[5]].y])
        ear = (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * np.linalg.norm(p1 - p4))
        return ear

    def _check_attention_drop_mesh(self, landmarks, face_idx):
        state = self.face_states.get(face_idx)
        if not state: return False, ""
        
        left_eye_idx = [33, 160, 158, 133, 153, 144]
        right_eye_idx = [362, 385, 387, 263, 373, 380]
        
        left_ear = self._calculate_ear(landmarks, left_eye_idx)
        right_ear = self._calculate_ear(landmarks, right_eye_idx)
        avg_ear = (left_ear + right_ear) / 2.0
        
        if avg_ear < self.ear_threshold:
            state["closed_eyes_frames"] += 1
        else:
            state["closed_eyes_frames"] = 0
            
        if state["closed_eyes_frames"] > 15:
            return True, "SLEEPING (EYES CLOSED)"
            
        nose = landmarks[1]
        left_cheek = landmarks[234]
        right_cheek = landmarks[454]
        
        face_width = abs(left_cheek.x - right_cheek.x)
        if face_width > 0.02:
            nose_to_left = abs(nose.x - left_cheek.x)
            nose_to_right = abs(nose.x - right_cheek.x)
            ratio = min(nose_to_left, nose_to_right) / face_width
            if ratio < 0.15:
                return True, "ATTENTION DROP"
                
        eye_y = (landmarks[33].y + landmarks[362].y) / 2.0
        if nose.y > eye_y + 0.08:
            return True, "ATTENTION DROP"
            
        return False, ""

    def release(self):
        if self.use_mediapipe:
            if hasattr(self, 'face_detection') and self.face_detection:
                self.face_detection.close()
            if hasattr(self, 'face_mesh') and self.face_mesh:
                self.face_mesh.close()