"""
pytest 공통 설정.

PR#1: 기본 smoke test용 세팅만.
PR#2: PostgreSQL 테스트 DB fixture 추가 예정.
"""

# 모든 SQLAlchemy 모델을 Base.metadata에 등록
# (향후 fixture에서 create_all() 호출 시 필요)
from app import models  # noqa: F401