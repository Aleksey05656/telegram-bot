## @file: script.py.mako
## @description: Alembic revision template for async migrations.
## @dependencies: alembic
## @created: 2025-09-17
<%!
from alembic import op
import sqlalchemy as sa
%>

"""${message}"

revision = ${repr(revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


async def upgrade() -> None:
    """Apply the migration."""
    pass


async def downgrade() -> None:
    """Rollback the migration."""
    pass
