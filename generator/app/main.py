from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.scheduler import start_scheduler, stop_scheduler
from app.generators.log_generator import LogGenerator
from app.generators.event_generator import EventGenerator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    start_scheduler()
    yield
    # 종료 시
    stop_scheduler()


app = FastAPI(
    title="Data Generator",
    description="분산처리 파이프라인용 데이터 생성기",
    version="0.1.0",
    lifespan=lifespan
)

log_generator = LogGenerator()
event_generator = EventGenerator()


@app.get("/")
async def root():
    return {
        "service": "Data Generator",
        "status": "running",
        "config": {
            "backend_url": settings.backend_url,
            "log_interval": settings.log_interval_seconds,
            "event_interval": settings.event_interval_seconds,
            "batch_size": settings.batch_size
        }
    }


@app.get("/health")
async def health():
    return {"status": "UP"}


@app.get("/sample/log")
async def sample_log():
    """샘플 로그 1개 생성"""
    return log_generator.generate_one()


@app.get("/sample/logs")
async def sample_logs(count: int = 10):
    """샘플 로그 여러개 생성"""
    return log_generator.generate_batch(count)


@app.get("/sample/event")
async def sample_event():
    """샘플 이벤트 1개 생성"""
    return event_generator.generate_one()


@app.get("/sample/events")
async def sample_events(count: int = 10):
    """샘플 이벤트 여러개 생성"""
    return event_generator.generate_batch(count)


@app.post("/trigger/logs")
async def trigger_logs():
    """수동으로 로그 배치 전송"""
    from app.scheduler import send_logs
    await send_logs()
    return {"status": "triggered", "type": "logs"}


@app.post("/trigger/events")
async def trigger_events():
    """수동으로 이벤트 배치 전송"""
    from app.scheduler import send_events
    await send_events()
    return {"status": "triggered", "type": "events"}
