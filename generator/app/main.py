from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings
from app.scheduler import start_scheduler, stop_scheduler, update_scheduler, get_scheduler_status
from app.generators.log_generator import LogGenerator
from app.generators.event_generator import EventGenerator

import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Data Generator",
    description="분산처리 파이프라인용 데이터 생성기",
    version="0.3.0",
    lifespan=lifespan
)

log_generator = LogGenerator()
event_generator = EventGenerator()


# ============ 기본 엔드포인트 ============

@app.get("/")
async def root():
    return {
        "service": "Data Generator",
        "status": "running",
        "endpoints": {
            "control": ["/control/start", "/control/stop", "/control/status"],
            "burst": ["/burst/logs", "/burst/events"],
            "sample": ["/sample/log", "/sample/logs", "/sample/event", "/sample/events"]
        }
    }


@app.get("/health")
async def health():
    return {"status": "UP"}


# ============ 제어 엔드포인트 ============

@app.post("/control/start")
async def control_start(
    batch_size: int = 100,
    log_interval: float = 5.0,
    event_interval: float = 10.0
):
    """스케줄러 시작/업데이트"""
    result = update_scheduler(batch_size, log_interval, event_interval)
    return result


@app.post("/control/stop")
async def control_stop():
    """스케줄러 중지"""
    stop_scheduler()
    return {"status": "stopped"}


@app.get("/control/status")
async def control_status():
    """현재 상태 확인"""
    return get_scheduler_status()


# ============ Burst 엔드포인트 (즉시 대량 전송) ============

@app.post("/burst/logs")
async def burst_logs(count: int = 1000, batch_size: int = 100):
    """즉시 N건의 로그 전송"""
    sent = 0
    errors = 0
    
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, count, batch_size):
            current_batch = min(batch_size, count - i)
            logs = log_generator.generate_batch(current_batch)
            
            try:
                response = await client.post(
                    f"{settings.backend_url}/api/collect/logs",
                    json=logs
                )
                response.raise_for_status()
                sent += current_batch
            except Exception as e:
                errors += 1
                logger.error(f"Burst logs error: {e}")
    
    return {
        "status": "completed",
        "requested": count,
        "sent": sent,
        "errors": errors
    }


@app.post("/burst/events")
async def burst_events(count: int = 1000, batch_size: int = 100):
    """즉시 N건의 이벤트 전송"""
    sent = 0
    errors = 0
    
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, count, batch_size):
            current_batch = min(batch_size, count - i)
            events = event_generator.generate_batch(current_batch)
            
            try:
                response = await client.post(
                    f"{settings.backend_url}/api/collect/activities",
                    json=events
                )
                response.raise_for_status()
                sent += current_batch
            except Exception as e:
                errors += 1
                logger.error(f"Burst events error: {e}")
    
    return {
        "status": "completed",
        "requested": count,
        "sent": sent,
        "errors": errors
    }


@app.post("/burst/mixed")
async def burst_mixed(log_count: int = 1000, event_count: int = 500, batch_size: int = 100):
    """로그 + 이벤트 동시 대량 전송"""
    log_result = await burst_logs(log_count, batch_size)
    event_result = await burst_events(event_count, batch_size)
    
    return {
        "logs": log_result,
        "events": event_result,
        "total_sent": log_result["sent"] + event_result["sent"]
    }


# ============ 샘플 엔드포인트 ============

@app.get("/sample/log")
async def sample_log():
    return log_generator.generate_one()


@app.get("/sample/logs")
async def sample_logs(count: int = 10):
    return log_generator.generate_batch(count)


@app.get("/sample/event")
async def sample_event():
    return event_generator.generate_one()


@app.get("/sample/events")
async def sample_events(count: int = 10):
    return event_generator.generate_batch(count)
