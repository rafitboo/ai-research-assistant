"""merge conflicting heads

Revision ID: 82c1336d9a17
Revises: 012497c29386
Create Date: 2026-08-17 23:02:52.670432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82c1336d9a17'
down_revision: Union[str, Sequence[str], None] = '012497c29386'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
