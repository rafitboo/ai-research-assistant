"""merge conflicting heads

Revision ID: 012497c29386
Revises: 606c782f0c96, f7e5d4e49f55
Create Date: 2026-08-17 22:58:12.673513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012497c29386'
down_revision: Union[str, Sequence[str], None] = ('606c782f0c96', 'f7e5d4e49f55')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
