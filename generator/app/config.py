from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Backend API 설정 - K8s 환경변수 우선
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8081")
    backend_timeout: int = 30

    # 배치 스케줄 설정
    log_interval_seconds: int = 5
    event_interval_seconds: int = 10
    batch_size: int = 100

    # 생성 데이터 설정
    services: list = ["api-gateway", "user-service", "order-service", "payment-service"]
    log_levels: list = ["INFO", "DEBUG", "WARN", "ERROR"]
    event_types: list = ["CLICK", "VIEW", "PURCHASE", "LOGIN", "LOGOUT", "SEARCH"]

    # 에러 비율 (0.0 ~ 1.0)
    error_rate: float = 0.05

    class Config:
        env_file = ".env"
        env_prefix = "GENERATOR_"


settings = Settings()
