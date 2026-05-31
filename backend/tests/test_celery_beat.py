"""Celery Beat 스케줄 등록 검증 단위 테스트."""

def test_beat_schedule_has_three_sources():
    from app.worker.celery_app import celery_app

    schedules = celery_app.conf.beat_schedule
    expected = {"daily-bizinfo-collect", "daily-kstartup-collect", "daily-mss-collect"}
    assert set(schedules.keys()) == expected

    for name, conf in schedules.items():
        assert conf["task"] == "app.worker.tasks.collect_source"
        assert "schedule" in conf
        assert isinstance(conf["args"], tuple)
        assert len(conf["args"]) == 1
        assert conf["args"][0] in {"bizinfo", "kstartup", "mss"}

def test_timezone_is_seoul():
    from app.worker.celery_app import celery_app
    assert celery_app.conf.timezone == "Asia/Seoul"
