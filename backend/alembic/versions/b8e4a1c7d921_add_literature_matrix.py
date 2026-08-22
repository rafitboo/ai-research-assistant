"""Add literature comparison matrix

Revision ID: b8e4a1c7d921_add_literature_matrix
Revises: 9a1f3c7d2b44
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4a1c7d921"
down_revision: Union[str, Sequence[str], None] = "9a1f3c7d2b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(  
        "literature_matrices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Literature Comparison Matrix"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now())  
    )
    op.create_index("ix_literature_matrices_project_id", "literature_matrices", ["project_id"])

    op.create_table(  
        "literature_matrix_papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("matrix_id", sa.Integer(), sa.ForeignKey("literature_matrices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0")  
    )
    op.create_index("ix_literature_matrix_papers_matrix_id", "literature_matrix_papers", ["matrix_id"])
    op.create_index("ix_literature_matrix_papers_paper_id", "literature_matrix_papers", ["paper_id"])

    op.create_table(  
        "literature_matrix_columns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("matrix_id", sa.Integer(), sa.ForeignKey("literature_matrices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_custom", sa.Integer(), nullable=False, server_default="0")  
    )
    op.create_index("ix_literature_matrix_columns_matrix_id", "literature_matrix_columns", ["matrix_id"])

    op.create_table(  
        "literature_matrix_cells",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("matrix_id", sa.Integer(), sa.ForeignKey("literature_matrices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_id", sa.Integer(), sa.ForeignKey("literature_matrix_columns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="AI"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now())  
    )
    op.create_index("ix_literature_matrix_cells_matrix_id", "literature_matrix_cells", ["matrix_id"])
    op.create_index("ix_literature_matrix_cells_paper_id", "literature_matrix_cells", ["paper_id"])
    op.create_index("ix_literature_matrix_cells_column_id", "literature_matrix_cells", ["column_id"])

def downgrade() -> None:

    op.drop_index(
        "ix_literature_matrix_cells_column_id",
        table_name="literature_matrix_cells"
    )

    op.drop_index(
        "ix_literature_matrix_cells_paper_id",
        table_name="literature_matrix_cells"
    )

    op.drop_index(
        "ix_literature_matrix_cells_matrix_id",
        table_name="literature_matrix_cells"
    )

    op.drop_table("literature_matrix_cells")

    op.drop_index(
        "ix_literature_matrix_columns_matrix_id",
        table_name="literature_matrix_columns"
    )

    op.drop_table("literature_matrix_columns")

    op.drop_index(
        "ix_literature_matrix_papers_paper_id",
        table_name="literature_matrix_papers"
    )

    op.drop_index(
        "ix_literature_matrix_papers_matrix_id",
        table_name="literature_matrix_papers"
    )

    op.drop_table("literature_matrix_papers")

    op.drop_index(
        "ix_literature_matrices_project_id",
        table_name="literature_matrices"
    )

    op.drop_table("literature_matrices")