import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

from faker import Faker

from app.config import settings

fake = Faker()


class LogGenerator:
    def __init__(self):
        self.services = settings.services
        self.log_levels = settings.log_levels
        self.error_rate = settings.error_rate

    def _get_log_level(self) -> str:
        if random.random() < self.error_rate:
            return "ERROR"
        return random.choice(["INFO", "DEBUG", "WARN"])

    def _generate_message(self, level: str, service: str) -> str:
        messages = {
            "INFO": [
                f"Request processed successfully",
                f"User authenticated",
                f"Cache hit for key",
                f"Connection established",
            ],
            "DEBUG": [
                f"Processing request payload",
                f"Query executed in database",
                f"Cache lookup performed",
            ],
            "WARN": [
                f"Slow query detected",
                f"Retry attempt",
                f"Connection pool running low",
            ],
            "ERROR": [
                f"Failed to process request",
                f"Database connection timeout",
                f"Service unavailable",
                f"Authentication failed",
            ],
        }
        return random.choice(messages.get(level, messages["INFO"]))

    def generate_one(self) -> Dict[str, Any]:
        service = random.choice(self.services)
        level = self._get_log_level()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": service,
            "host": f"worker-{random.randint(1, 3)}",
            "message": self._generate_message(level, service),
            "metadata": {
                "request_id": str(uuid.uuid4()),
                "response_time_ms": random.randint(10, 500) if level != "ERROR" else random.randint(500, 5000),
                "status_code": 200 if level != "ERROR" else random.choice([400, 500, 502, 503]),
                "endpoint": random.choice(["/api/users", "/api/orders", "/api/products", "/api/payments"]),
                "method": random.choice(["GET", "POST", "PUT", "DELETE"]),
            }
        }

    def generate_batch(self, size: int = None) -> List[Dict[str, Any]]:
        batch_size = size or settings.batch_size
        return [self.generate_one() for _ in range(batch_size)]
