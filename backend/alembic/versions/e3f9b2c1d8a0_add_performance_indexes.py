"""add performance indexes

Revision ID: e3f9b2c1d8a0
Revises: aec7f0aa570e
Create Date: 2026-05-21 20:14:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "e3f9b2c1d8a0"
down_revision = "adcb7cd716a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 마감일 기반 필터링 (D-day 배지, 마감 임박 정렬)
    op.create_index("ix_announcements_period_end", "announcements", ["period_end"])

    # 지역 기반 필터링 (방정우 회사별 페이지 필터)
    op.create_index("ix_announcements_region", "announcements", ["region"])

    # 매칭 대시보드 통계 (company_id + status 조합 쿼리)
    op.create_index(
        "ix_match_results_company_status",
        "match_results",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_match_results_company_status", table_name="match_results")
    op.drop_index("ix_announcements_region", table_name="announcements")
    op.drop_index("ix_announcements_period_end", table_name="announcements")
