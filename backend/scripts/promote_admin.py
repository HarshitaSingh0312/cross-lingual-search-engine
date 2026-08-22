"""Promote an existing user to admin by email. Manual, out-of-band by design —
signup can never set role=admin itself, so this is how the first admin gets made.

Run:
    python scripts/promote_admin.py someone@example.com
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.models import User, UserRole  # noqa: E402

settings = get_settings()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/promote_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    engine = create_engine(settings.sync_database_url)
    with Session(engine) as session:
        result = session.execute(
            update(User).where(User.email == email).values(role=UserRole.admin)
        )
        session.commit()

        if result.rowcount == 0:
            print(f"No user found with email {email}")
            sys.exit(1)
        print(f"{email} is now an admin.")


if __name__ == "__main__":
    main()
