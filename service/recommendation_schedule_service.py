"""Read, validate and persist the AI recommendation schedule."""
from datetime import datetime, timedelta, timezone
from domain.recommendation_schedule import RecommendationScheduleUpdate
from repository import settings_repository

SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")
LAST_RUN_KEY = "ai_recommendation_last_run_at"
CHANGE_KEY = "ai_recommendation_schedule_changed_at"

def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None

def get_config() -> RecommendationScheduleUpdate:
    values = settings_repository.get_all()
    return RecommendationScheduleUpdate(
        mode=values["ai_recommendation_schedule_mode"],
        dailyTime=values["ai_recommendation_daily_time"],
        intervalMinutes=int(values["ai_recommendation_interval_minutes"]),
    )

def get_last_run() -> datetime | None:
    return _parse_timestamp(settings_repository.get_value(LAST_RUN_KEY))

def get_schedule_revision() -> str | None:
    return settings_repository.get_value(CHANGE_KEY)

def calculate_next_run(config: RecommendationScheduleUpdate, now: datetime | None = None) -> datetime:
    current = (now or datetime.now(timezone.utc)).astimezone(SEOUL)
    if config.mode == "INTERVAL":
        last_run = get_last_run()
        changed_at = _parse_timestamp(get_schedule_revision())
        interval = timedelta(minutes=config.intervalMinutes)
        anchor = max((value for value in (last_run, changed_at) if value), default=None)
        candidate = anchor.astimezone(SEOUL) + interval if anchor else current + interval
        return candidate if candidate >= current else current + interval
    hour, minute = (int(part) for part in config.dailyTime.split(":"))
    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate if candidate >= current else candidate + timedelta(days=1)

def get_schedule() -> dict:
    config = get_config()
    return {**config.model_dump(), "timezone": "Asia/Seoul", "lastRunAt": get_last_run(), "nextRunAt": calculate_next_run(config)}

def save_schedule(payload: RecommendationScheduleUpdate, admin_id: int) -> dict:
    settings_repository.save_all({
        "ai_recommendation_schedule_mode": payload.mode,
        "ai_recommendation_daily_time": payload.dailyTime,
        "ai_recommendation_interval_minutes": payload.intervalMinutes,
        CHANGE_KEY: datetime.now(timezone.utc).isoformat(),
    }, admin_id)
    return get_schedule()

def record_run(completed_at: datetime) -> None:
    settings_repository.save_all({LAST_RUN_KEY: completed_at.astimezone(timezone.utc).isoformat()}, None)
