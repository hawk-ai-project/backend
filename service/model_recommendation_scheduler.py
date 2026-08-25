import asyncio
from contextlib import suppress

from config import settings
from service import model_recommendation_service


async def run(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(model_recommendation_service.refresh_cached_recommendations)
        except Exception as error:
            print(f"[MODEL RECOMMENDATION SCHEDULER FAILED] {error}")
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=settings.model_recommendation_refresh_seconds)
