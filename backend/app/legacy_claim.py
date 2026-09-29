"""Issue a one-time claim code for an existing local passwordless record.

Run locally with: python -m app.legacy_claim --email ADDRESS
"""

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth_core import issue_legacy_claim
from app.database import get_engine
from app.models import User


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a one-time local legacy account claim code")
    parser.add_argument("--email", required=True, help="Email on the old FinApp user record")
    args = parser.parse_args(argv)
    email = args.email.strip().lower()
    with Session(get_engine()) as db:
        with db.begin():
            user = db.scalar(select(User).where(func.lower(User.email) == email).with_for_update())
            if user is None or user.password_hash:
                print("No unclaimed local record has that email.", file=sys.stderr)
                return 1
            code = issue_legacy_claim(user)
    print(f"Claim code: {code}")
    print("Enter this code in FinApp within 30 minutes. It is shown only now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
