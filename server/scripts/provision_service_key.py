"""Provision a non-admin (member) service user + API key. Run inside the miman container:

    docker exec <container> python -m scripts.provision_service_key \
        --name finsor-runtime --label "finsor prod runtime"

Prints the full API key ONCE to stdout (nowhere else, never logged). The base ships no
path to a non-admin principal — /auth/register creates only the first user hardcoded
role="admin" and User.role defaults "admin" (spec 03-M §3.4 delta-6) — so this deploy-time
tool mints the per-consumer runtime credential the credential-class model depends on.
Mirrors server/scripts/reset_admin_password.py: zero API-surface change, uses existing
upstream helpers, never touches auth.py or the routers.
"""

import argparse
import sys

from sqlalchemy import select

from auth import generate_api_key
from db import SessionLocal
from models import APIKey, User

SERVICE_EMAIL_DOMAIN = "svc.miman.local"


def _service_email(name: str) -> str:
    """Deterministic, unique email for a service user (User.email is unique/non-null,
    models.py:23) — also the idempotency key: one member user per --name."""
    return f"{name.strip().lower()}@{SERVICE_EMAIL_DOMAIN}"


def provision(db, name: str, label: str, rotate: bool = False) -> tuple[str, bool]:
    """Create a member service user (or rotate its key). Returns (full_key, created_user).

    Idempotent by name: an existing service user is refused unless --rotate, in which case
    only a new key is minted (no second user). Raises ValueError on refusal — the caller
    commits nothing, so a refusal writes nothing.
    """
    email = _service_email(name)
    user = db.scalar(select(User).where(User.email == email))
    created = False
    if user is None:
        user = User(name=name, email=email, password_hash="", role="member")
        db.add(user)
        db.flush()  # assign user.id before the FK below
        created = True
    elif not rotate:
        raise ValueError(f"service user {name!r} already exists; pass --rotate to mint a new key")

    full_key, prefix, key_hash = generate_api_key()
    db.add(APIKey(key_prefix=prefix, key_hash=key_hash, label=label, created_by=user.id))
    db.commit()
    return full_key, created


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Provision a member (non-admin) service API key.")
    parser.add_argument("--name", required=True, help="Service identity (idempotency key).")
    parser.add_argument("--label", required=True, help="Human label recorded on the API key.")
    parser.add_argument("--rotate", action="store_true", help="Mint a new key for an existing service user.")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            full_key, created = provision(db, args.name, args.label, args.rotate)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3

    verb = "Created" if created else "Rotated key for"
    print(f"{verb} member service user {args.name!r} (role=member).", file=sys.stderr)
    print(full_key)  # stdout, once — the only place the key is ever emitted
    return 0


if __name__ == "__main__":
    sys.exit(main())
