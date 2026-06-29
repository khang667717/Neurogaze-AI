import uuid

class EventGenerator:
    def __init__(self, session_id):
        self.session_id = session_id
        
    def generate_events(self, detection_result, timestamp):
        """
        Translates detection results into standard SRVAS JSON events.
        Returns a list of event dictionaries.
        """
        events = []
        face_events = detection_result.get("face_events", [])
        
        # Base event template
        def make_event(event_code):
            return {
                "event_id": str(uuid.uuid4()),
                "session_id": self.session_id,
                "event_code": event_code,
                "timestamp": timestamp,
                "confidence": 1.0, # Confidence is handled directly via event generation for MVP
                "payload": detection_result.get("pose_data", {})
            }

        if len(face_events) == 0:
            events.append(make_event("NO_PERSON"))
        else:
            for event_code in face_events:
                events.append(make_event(event_code))
                
        return events
