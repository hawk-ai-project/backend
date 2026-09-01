import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import pymysql
from common.db import engine
from service import model_recommendation_service, recommendation_schedule_service

POLL_SECONDS = 5
LOCK_NAME = "hawk_ai_model_recommendation_scheduler"

def _refresh_with_lock() -> bool:
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (LOCK_NAME,))
            row = cursor.fetchone()
            if not row or row["acquired"] != 1:
                return False
            try:
                model_recommendation_service.refresh_cached_recommendations()
                recommendation_schedule_service.record_run(datetime.now(timezone.utc))
                return True
            finally:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
    finally:
        connection.close()

async def run(stop_event: asyncio.Event) -> None:
    signature = None
    next_run = None
    while not stop_event.is_set():
        try:
            config = await asyncio.to_thread(recommendation_schedule_service.get_config)
            revision = await asyncio.to_thread(recommendation_schedule_service.get_schedule_revision)
            current_signature = (config.mode, config.dailyTime, config.intervalMinutes, revision)
            if current_signature != signature or next_run is None:
                signature = current_signature
                next_run = await asyncio.to_thread(recommendation_schedule_service.calculate_next_run, config)
            now = datetime.now(timezone.utc)
            if next_run.astimezone(timezone.utc) <= now:
                await asyncio.to_thread(_refresh_with_lock)
                next_run = await asyncio.to_thread(recommendation_schedule_service.calculate_next_run, config)
                continue
            delay = min(POLL_SECONDS, max(0.1, (next_run.astimezone(timezone.utc) - now).total_seconds()))
        except Exception as error:
            print(f"[MODEL RECOMMENDATION SCHEDULER FAILED] {error}")
            delay = POLL_SECONDS
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
