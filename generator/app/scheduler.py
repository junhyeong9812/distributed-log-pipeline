import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.generators.log_generator import LogGenerator
from app.generators.event_generator import EventGenerator

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

log_generator = LogGenerator()
event_generator = EventGenerator()

scheduler = AsyncIOScheduler()

# 현재 설정 상태
current_config = {
    "running": False,
    "batch_size": 100,
    "log_interval": 5.0,
    "event_interval": 10.0,
    "logs_sent": 0,
    "events_sent": 0,
    "errors": 0
}


async def send_logs():
    """로그 배치 생성 및 전송"""
    try:
        logs = log_generator.generate_batch(current_config["batch_size"])
        
        async with httpx.AsyncClient(timeout=settings.backend_timeout) as client:
            response = await client.post(
                f"{settings.backend_url}/api/collect/logs",
                json=logs
            )
            response.raise_for_status()
        
        current_config["logs_sent"] += len(logs)
        logger.info(f"Sent {len(logs)} logs - Total: {current_config['logs_sent']}")
        
    except Exception as e:
        current_config["errors"] += 1
        logger.error(f"Failed to send logs: {e}")


async def send_events():
    """이벤트 배치 생성 및 전송"""
    try:
        events = event_generator.generate_batch(current_config["batch_size"])
        
        async with httpx.AsyncClient(timeout=settings.backend_timeout) as client:
            response = await client.post(
                f"{settings.backend_url}/api/collect/activities",
                json=events
            )
            response.raise_for_status()
        
        current_config["events_sent"] += len(events)
        logger.info(f"Sent {len(events)} events - Total: {current_config['events_sent']}")
        
    except Exception as e:
        current_config["errors"] += 1
        logger.error(f"Failed to send events: {e}")


def update_scheduler(batch_size: int, log_interval: float, event_interval: float):
    """스케줄러 설정 업데이트"""
    global current_config
    
    # 기존 작업 제거
    try:
        scheduler.remove_job("log_job")
        scheduler.remove_job("event_job")
    except:
        pass
    
    # 설정 업데이트
    current_config["batch_size"] = batch_size
    current_config["log_interval"] = log_interval
    current_config["event_interval"] = event_interval
    current_config["running"] = True
    
    # 새 작업 추가
    scheduler.add_job(
        send_logs,
        trigger=IntervalTrigger(seconds=log_interval),
        id="log_job",
        name="Log Generator Job",
        replace_existing=True
    )
    
    scheduler.add_job(
        send_events,
        trigger=IntervalTrigger(seconds=event_interval),
        id="event_job",
        name="Event Generator Job",
        replace_existing=True
    )
    
    if not scheduler.running:
        scheduler.start()
    
    # 처리량 계산
    logs_per_min = int((batch_size / log_interval) * 60)
    events_per_min = int((batch_size / event_interval) * 60)
    
    logger.info(f"Scheduler updated - batch:{batch_size}, log_interval:{log_interval}s, event_interval:{event_interval}s")
    logger.info(f"Throughput: {logs_per_min} logs/min, {events_per_min} events/min")
    
    return {
        "status": "started",
        "config": {
            "batch_size": batch_size,
            "log_interval": log_interval,
            "event_interval": event_interval
        },
        "throughput": {
            "logs_per_minute": logs_per_min,
            "events_per_minute": events_per_min,
            "total_per_minute": logs_per_min + events_per_min
        }
    }


def start_scheduler():
    """기본 설정으로 스케줄러 시작"""
    return update_scheduler(
        current_config["batch_size"],
        current_config["log_interval"],
        current_config["event_interval"]
    )


def stop_scheduler():
    """스케줄러 중지"""
    global current_config
    
    try:
        scheduler.remove_job("log_job")
        scheduler.remove_job("event_job")
    except:
        pass
    
    current_config["running"] = False
    logger.info("Scheduler stopped")


def get_scheduler_status():
    """현재 상태 반환"""
    logs_per_min = int((current_config["batch_size"] / current_config["log_interval"]) * 60) if current_config["running"] else 0
    events_per_min = int((current_config["batch_size"] / current_config["event_interval"]) * 60) if current_config["running"] else 0
    
    return {
        "running": current_config["running"],
        "config": {
            "batch_size": current_config["batch_size"],
            "log_interval": current_config["log_interval"],
            "event_interval": current_config["event_interval"]
        },
        "throughput": {
            "logs_per_minute": logs_per_min,
            "events_per_minute": events_per_min,
            "total_per_minute": logs_per_min + events_per_min
        },
        "stats": {
            "logs_sent": current_config["logs_sent"],
            "events_sent": current_config["events_sent"],
            "errors": current_config["errors"]
        }
    }
