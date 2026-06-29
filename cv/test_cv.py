import pytest
import time
import sys
import os
sys.path.append(os.path.dirname(__file__))

from detector import BehaviorDetector
from event_generator import EventGenerator

def test_event_generator_initialization():
    generator = EventGenerator("test_session_123")
    assert generator.session_id == "test_session_123"

def test_event_generator_no_person():
    generator = EventGenerator("test_session_123")
    mock_detection = {
        "person_detected": False,
        "attention_drop": False,
        "is_idle": False,
        "confidence": 0.0
    }
    events = generator.generate_events(mock_detection, time.time())
    assert len(events) == 1
    assert events[0]['event_code'] == 'NO_PERSON'

def test_detector_initialization():
    # Only test initialization without running heavy mediapipe
    detector = BehaviorDetector()
    assert detector is not None
    # Ensure release does not crash if mediapipe is not properly setup
    try:
        detector.release()
    except Exception as e:
        pytest.fail(f"detector.release() raised {type(e).__name__} unexpectedly!")
