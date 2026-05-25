from celery import Celery

from app.config import settings

celery_app = Celery(
    "docjipge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10분 (LLM 호출 + 첨부파일 변환 고려)
    task_soft_time_limit=540,
    task_default_rate_limit="30/m",  # concurrency=4 환경에서 OpenAI rate limit 폭증 방지
)
