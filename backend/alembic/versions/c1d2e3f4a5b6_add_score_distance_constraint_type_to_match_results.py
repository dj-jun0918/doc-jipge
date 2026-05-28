"""add score, distance, constraint_type to match_results

Revision ID: c1d2e3f4a5b6
Revises: aec7f0aa570e
Create Date: 2026-05-20 12:00:00.000000

매칭 알고리즘 정교화 — 컬럼 추가
- score: float | None — 필드별 score (0~1)
- distance: float | None — 미충족 수치 필드의 정규화 거리
- constraint_type: str | None — "hard" / "soft"
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'aec7f0aa570e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('match_results', sa.Column('score', sa.Float(), nullable=True))
    op.add_column('match_results', sa.Column('distance', sa.Float(), nullable=True))
    op.add_column('match_results', sa.Column('constraint_type', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('match_results', 'constraint_type')
    op.drop_column('match_results', 'distance')
    op.drop_column('match_results', 'score')
