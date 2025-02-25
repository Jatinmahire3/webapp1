"""Added review_count column to doctor model

Revision ID: c239bec7c5de
Revises: 
Create Date: 2025-01-15 23:21:32.802979
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c239bec7c5de'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### Add review_count column to doctor_profile_details with default value 0 ###
    op.add_column('doctor_profile_details', sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'))

    # ### Create review table ###
    op.create_table('review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['user.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Add a unique constraint on user_id in doctor_profile_details ###
    with op.batch_alter_table('doctor_profile_details', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_doctor_user_id', ['user_id'])  # Explicit constraint name


def downgrade():
    # ### Drop the review_count column from doctor_profile_details ###
    op.drop_column('doctor_profile_details', 'review_count')

    # ### Drop review table ###
    op.drop_table('review')

    # ### Drop the unique constraint from doctor_profile_details ###
    with op.batch_alter_table('doctor_profile_details', schema=None) as batch_op:
        batch_op.drop_constraint('uq_doctor_user_id', type_='unique')  # Drop the unique constraint by name
