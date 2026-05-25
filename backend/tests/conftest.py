"""pytest 공통 설정.

PR#1: 기본 smoke test용 세팅만.
PR#4: DB 세션 + FastAPI TestClient fixture 추가.

- `db_engine`: session-scoped, `docjipge_test` DB에 모든 테이블 생성/해제
- `db_session`: function-scoped, SAVEPOINT 패턴으로 테스트마다 롤백
- `client`: function-scoped, FastAPI TestClient + `get_db` override
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# 모든 SQLAlchemy 모델을 Base.metadata에 등록
from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app

# 테스트 DB URL — docker compose 안에서 실행할 때는 'db:5432', 호스트에서 직접 실행 시 'localhost:5432'
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:password@db:5432/docjipge_test",
)


@pytest.fixture(scope="session")
def db_engine():
    """테스트 DB 엔진 — 세션 시작 시 테이블 생성, 종료 시 drop."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """function-scoped 세션 — SAVEPOINT 기반 롤백.

    프로덕션 코드가 db.commit()을 호출해도 outer transaction은 유지되어
    테스트 종료 시 모든 변경이 롤백된다.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    # SAVEPOINT 시작 (commit이 SAVEPOINT release로 변환됨)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient — get_db를 테스트 세션으로 override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

