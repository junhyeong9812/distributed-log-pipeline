from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Backend API 설정 - K8s 환경변수 우선
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8081")
    backend_timeout: int = int(os.getenv("BACKEND_TIMEOUT", "30"))

    # 배치 스케줄 설정 - 환경변수로 동적 조절 가능
    log_interval_seconds: float = float(os.getenv("LOG_INTERVAL", "5"))
    event_interval_seconds: float = float(os.getenv("EVENT_INTERVAL", "10"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "100"))

    # 생성 데이터 설정
    services: list = ["api-gateway", "user-service", "order-service", "payment-service"]
    log_levels: list = ["INFO", "DEBUG", "WARN", "ERROR"]
    event_types: list = ["CLICK", "VIEW", "PURCHASE", "LOGIN", "LOGOUT", "SEARCH"]

    # 에러 비율 (0.0 ~ 1.0)
    error_rate: float = float(os.getenv("ERROR_RATE", "0.05"))

    class Config:
        env_file = ".env"
        env_prefix = "GENERATOR_"


settings = Settings()

# 계산된 처리량 출력용
def get_throughput_info():
    logs_per_min = (settings.batch_size / settings.log_interval_seconds) * 60
    events_per_min = (settings.batch_size / settings.event_interval_seconds) * 60
    return {
        "batch_size": settings.batch_size,
        "log_interval": settings.log_interval_seconds,
        "event_interval": settings.event_interval_seconds,
        "logs_per_minute": int(logs_per_min),
        "events_per_minute": int(events_per_min),
        "total_per_minute": int(logs_per_min + events_per_min)
    }
