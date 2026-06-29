import time
import json
import uuid

class EventGenerator:
    def __init__(self):
        self.last_event_time = 0
        self.last_event_code = None
        self.session_id = str(uuid.uuid4())
        self.ttl = 1.0 # 1 second deduplication

    def emit(self, event_code, confidence=1.0, payload=None):
        now = time.time()
        
        # Deduplication: if same event happens within TTL, ignore it
        # EXCEPT for PERSON_DETECTED which we might want to pulse, but for MVP let's deduplicate all
        # Actually, if we deduplicate PERSON_DETECTED, we won't get a continuous stream. 
        # But that's fine, the aggregator can just assume the state is the last event.
        if event_code == self.last_event_code and (now - self.last_event_time) < self.ttl:
            return None
            
        event = {
            "event_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "timestamp": now,
            "event_code": event_code,
            "confidence": round(confidence, 3),
            "payload": payload or {}
        }
        
        self.last_event_code = event_code
        self.last_event_time = now
        
        print(json.dumps(event))
        return event
