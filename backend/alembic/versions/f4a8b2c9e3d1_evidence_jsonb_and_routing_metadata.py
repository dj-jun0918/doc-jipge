"""evidence JSONB conversion and routing_metadata column

Revision ID: f4a8b2c9e3d1
Revises: e3f9b2c1d8a0
Create Date: 2026-05-27 14:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "f4a8b2c9e3d1"
down_revision = "e3f9b2c1d8a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. eligibility_results.evidence: Text → JSONB
    #    기존 text는 {"text": ..., "location": null} 형식으로 백필.
    #    NULL row는 자동으로 {"text": null, "location": null} 로 변환.
    op.execute(
        """
        ALTER TABLE eligibility_results
        ALTER COLUMN evidence TYPE JSONB
        USING jsonb_build_object('text', evidence, 'location', NULL)
        """
    )

    # 2. announcements.routing_metadata JSONB 컬럼 신규 (nullable)
    op.add_column(
        "announcements",
        sa.Column("routing_metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("announcements", "routing_metadata")

    # JSONB → Text 복원: text 키만 추출
    op.execute(
        """
        ALTER TABLE eligibility_results
        ALTER COLUMN evidence TYPE TEXT
        USING evidence->>'text'
        """
    )
