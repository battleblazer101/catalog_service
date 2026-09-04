# alembic/versions/0001_add_app_paths.py

"""add app paths

Revision ID: 0001_add_app_paths
Revises:
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_add_app_paths"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "app_paths",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "name",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "path",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "media_type",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "path",
            name="uq_app_paths_path",
        ),
    )

    op.create_index(
        "ix_app_paths_path",
        "app_paths",
        ["path"],
        unique=False,
    )

    op.create_index(
        "ix_app_paths_media_type",
        "app_paths",
        ["media_type"],
        unique=False,
    )


def downgrade():

    op.drop_index(
        "ix_app_paths_media_type",
        table_name="app_paths",
    )

    op.drop_index(
        "ix_app_paths_path",
        table_name="app_paths",
    )

    op.drop_table(
        "app_paths",
    )
