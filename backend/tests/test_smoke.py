"""
pytest 인프라가 정상 동작하는지 확인하는 smoke test.
"""

def test_smoke():
    assert 1 + 1 == 2

def test_imports():
    """주요 모듈 import가 에러 없이 되는지 확인."""
    from app.database import Base, SessionLocal
    from app.models import Announcement, Company

    assert Base is not None
    assert SessionLocal is not None
    assert Announcement is not None
    assert Company is not None