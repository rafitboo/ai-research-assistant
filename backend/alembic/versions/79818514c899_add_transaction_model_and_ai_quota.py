"""Add Transaction model and AI quota

Revision ID: 79818514c899
Revises: 6e492a9feb74
Create Date: 2026-08-20 21:54:16.376799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '79818514c899'
down_revision: Union[str, Sequence[str], None] = '6e492a9feb74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update the existing transactions table
    op.add_column('transactions', sa.Column('currency', sa.String(), nullable=True))
    op.add_column('transactions', sa.Column('transaction_ref', sa.String(), nullable=False))
    op.drop_index('ix_transactions_transaction_code', table_name='transactions')
    op.create_index(op.f('ix_transactions_transaction_ref'), 'transactions', ['transaction_ref'], unique=True)
    op.drop_column('transactions', 'transaction_code')
    op.drop_column('transactions', 'completed_at')

    # 2. Add AI quota tracking to users
    op.add_column('users', sa.Column('ai_quota_used', sa.Integer(), nullable=True, server_default='0'))

def downgrade() -> None:
    # Reverse operations
    op.drop_column('users', 'ai_quota_used')
    
    op.add_column('transactions', sa.Column('completed_at', sa.DateTime(timezone=True), autoincrement=False, nullable=True))
    op.add_column('transactions', sa.Column('transaction_code', sa.String(), autoincrement=False, nullable=True))
    op.drop_index(op.f('ix_transactions_transaction_ref'), table_name='transactions')
    op.create_index('ix_transactions_transaction_code', 'transactions', ['transaction_code'], unique=False)
    op.drop_column('transactions', 'transaction_ref')
    op.drop_column('transactions', 'currency')