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


async def send_logs():
    """로그 배치 생성 및 전송"""
    try:
        logs = log_generator.generate_batch()
        
        async with httpx.AsyncClient(timeout=settings.backend_timeout) as client:
            response = await client.post(
                f"{settings.backend_url}/api/collect/logs",
                json=logs
            )
            response.raise_for_status()
            
        logger.info(f"Sent {len(logs)} logs - Status: {response.status_code}")
        
    except httpx.RequestError as e:
        logger.error(f"Failed to send logs: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending logs: {e}")


async def send_events():
    """이벤트 배치 생성 및 전송"""
    try:
        events = event_generator.generate_batch()
        
        async with httpx.AsyncClient(timeout=settings.backend_timeout) as client:
            response = await client.post(
                f"{settings.backend_url}/api/collect/activities",
                json=events
            )
            response.raise_for_status()
            
        logger.info(f"Sent {len(events)} events - Status: {response.status_code}")
        
    except httpx.RequestError as e:
        logger.error(f"Failed to send events: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending events: {e}")


def start_scheduler():
    """스케줄러 시작"""
    scheduler.add_job(
        send_logs,
        trigger=IntervalTrigger(seconds=settings.log_interval_seconds),
        id="log_job",
        name="Log Generator Job",
        replace_existing=True
    )
    
    scheduler.add_job(
        send_events,
        trigger=IntervalTrigger(seconds=settings.event_interval_seconds),
        id="event_job",
        name="Event Generator Job",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started - Logs every {settings.log_interval_seconds}s, Events every {settings.event_interval_seconds}s")


def stop_scheduler():
    """스케줄러 중지"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
