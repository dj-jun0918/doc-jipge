from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg://postgres:password@db:5432/docjipge"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # 기업마당 API
    bizinfo_api_key: str = ""

    # K-Startup API
    kstartup_api_url: str = (
        "https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1/getAnnouncementInformation"
    )

    # LLM API
    openai_api_key: str = ""
    google_api_key: str = ""

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    model_config = {"env_file": ".env"}


settings = Settings()
