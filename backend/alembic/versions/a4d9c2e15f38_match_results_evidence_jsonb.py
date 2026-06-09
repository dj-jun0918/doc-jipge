"""match_results.evidence text -> jsonb (location 저장)

Revision ID: a4d9c2e15f38
Revises: f4a8b2c9e3d1
Create Date: 2026-06-03 10:00:00.000000

match_results.evidence를 text -> JSONB로 전환.
- 매칭 근거에 위치 정보(location)까지 저장 → 프론트 PDF page jump
- 기존 text 값은 {"text": <값>, "location": null}로 백필
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a4d9c2e15f38'
down_revision: Union[str, None] = 'f4a8b2c9e3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE match_results
        ALTER COLUMN evidence TYPE JSONB
        USING CASE
            WHEN evidence IS NULL THEN NULL
            ELSE jsonb_build_object('text', evidence, 'location', NULL)
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE match_results
        ALTER COLUMN evidence TYPE TEXT
        USING CASE
            WHEN evidence IS NULL THEN NULL
            ELSE evidence->>'text'
        END
        """
    )
