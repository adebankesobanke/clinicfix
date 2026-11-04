"""Add the optional User-MaintenanceStaff relationship.

Revision ID: 0002_user_maintenance_staff
Revises: 0001_original_schema
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers.
revision = "0002_user_maintenance_staff"
down_revision = "0001_original_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "maintenance_staff_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_user_maintenance_staff_id",
        "user",
        ["maintenance_staff_id"],
    )

    op.create_foreign_key(
        "fk_user_maintenance_staff_id",
        "user",
        "maintenance_staff",
        ["maintenance_staff_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "fk_user_maintenance_staff_id",
        "user",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_user_maintenance_staff_id",
        "user",
        type_="unique",
    )

    op.drop_column("user", "maintenance_staff_id")