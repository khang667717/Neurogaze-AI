import cv2
import mediapipe as mp
import time
import numpy as np
import sys
from event_generator import EventGenerator

def main():
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6)
    mp_drawing = mp.solutions.drawing_utils

    event_gen = EventGenerator()

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        sys.exit(1)

    # Set target FPS to 5
    target_fps = 5
    frame_time = 1.0 / target_fps

    prev_gray = None
    idle_threshold = 300000 # Pixel difference threshold, needs tuning based on resolution
    
    last_idle_time = time.time()
    IDLE_TIMEOUT = 3.0 # seconds of no motion to trigger IDLE

    print("Starting SRVAS Capture. Press ESC to exit.")

    while cap.isOpened():
        start_time = time.time()
        
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            time.sleep(0.1)
            continue

        # Resize image for faster processing (optional, keeps MVP light)
        image = cv2.resize(image, (640, 480))

        # 1. Motion Detection (Idle check)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        motion_detected = False
        if prev_gray is not None:
            frame_delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            diff_sum = np.sum(thresh)
            if diff_sum > idle_threshold:
                motion_detected = True
                last_idle_time = time.time()
                
        prev_gray = gray
        
        # 2. Pose Estimation
        # To improve performance, optionally mark the image as not writeable to pass by reference.
        image.flags.writeable = False
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)

        image.flags.writeable = True
        
        if results.pose_landmarks:
            # Draw the pose annotation on the image.
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
            landmarks = results.pose_landmarks.landmark
            nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
            left_ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR.value]
            right_ear = landmarks[mp_pose.PoseLandmark.RIGHT_EAR.value]
            
            attention_drop = False
            
            # Simple heuristic for "turned away"
            face_width = abs(left_ear.x - right_ear.x)
            nose_to_left = abs(nose.x - left_ear.x)
            nose_to_right = abs(nose.x - right_ear.x)
            
            if face_width > 0:
                ratio = min(nose_to_left, nose_to_right) / face_width
                # If the nose is very close to one ear, head is turned
                if ratio < 0.2: 
                    attention_drop = True
                    
            # Simple heuristic for "looking down"
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
            
            # If nose y is close to shoulder y, head is likely dropped
            if abs(nose.y - shoulder_y) < 0.15:
                attention_drop = True

            confidence = nose.visibility

            if attention_drop:
                event_gen.emit("ATTENTION_DROP", confidence=confidence)
            else:
                # Check for IDLE (present, but not moving)
                if not motion_detected and (time.time() - last_idle_time) > IDLE_TIMEOUT:
                    event_gen.emit("IDLE_DETECTED", confidence=confidence)
                else:
                    event_gen.emit("PERSON_DETECTED", confidence=confidence)
        else:
            event_gen.emit("NO_PERSON", confidence=1.0)

        # Show video
        cv2.imshow('SRVAS MVP', image)
        if cv2.waitKey(5) & 0xFF == 27: # ESC
            break
            
        # Manual throttle to target FPS
        elapsed = time.time() - start_time
        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
