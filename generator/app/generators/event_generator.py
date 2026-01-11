import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

from faker import Faker

from app.config import settings

fake = Faker()


class EventGenerator:
    def __init__(self):
        self.event_types = settings.event_types

    def _generate_device(self) -> Dict[str, str]:
        device_types = ["desktop", "mobile", "tablet"]
        os_list = ["Windows", "macOS", "iOS", "Android", "Linux"]
        browsers = ["Chrome", "Safari", "Firefox", "Edge"]
        
        return {
            "type": random.choice(device_types),
            "os": random.choice(os_list),
            "browser": random.choice(browsers),
        }

    def _generate_event_data(self, event_type: str) -> Dict[str, Any]:
        if event_type == "CLICK":
            return {
                "page": fake.uri_path(),
                "element": random.choice(["button", "link", "image", "card"]),
                "position": {"x": random.randint(0, 1920), "y": random.randint(0, 1080)},
            }
        elif event_type == "VIEW":
            return {
                "page": fake.uri_path(),
                "duration_seconds": random.randint(1, 300),
            }
        elif event_type == "PURCHASE":
            return {
                "product_id": f"prod_{random.randint(1000, 9999)}",
                "quantity": random.randint(1, 5),
                "price": round(random.uniform(10, 500), 2),
            }
        elif event_type == "SEARCH":
            return {
                "query": fake.word(),
                "results_count": random.randint(0, 100),
            }
        else:
            return {}

    def generate_one(self) -> Dict[str, Any]:
        event_type = random.choice(self.event_types)
        user_id = f"user_{random.randint(1, 1000)}"
        
        return {
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "userId": user_id,
            "sessionId": f"sess_{uuid.uuid4().hex[:8]}",
            "eventType": event_type,
            "eventData": self._generate_event_data(event_type),
            "device": self._generate_device(),
        }

    def generate_batch(self, size: int = None) -> List[Dict[str, Any]]:
        batch_size = size or settings.batch_size
        return [self.generate_one() for _ in range(batch_size)]
