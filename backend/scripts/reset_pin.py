"""Reset a creator's PIN directly against the database — for when a creator is locked out and
there's no other way in. Reuses `app.security.pin.hash_pin` instead of reimplementing PBKDF2, so
hash-format compatibility is guaranteed by construction rather than by keeping two implementations
in sync.

Usage:
    uv run python scripts/reset_pin.py --creator-id 1 --pin 1234
    uv run python scripts/reset_pin.py --name "Some Creator" --pin 1234

Run from `backend/` (or anywhere with the `backend` venv active) so `app` resolves via the
editable install `uv sync` sets up — same as `alembic/env.py`.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session_factory
from app.db.models import Creator
from app.security.pin import hash_pin


async def _reset(*, creator_id: int | None, name: str | None, pin: str) -> None:
    async with async_session_factory() as session:
        if creator_id is not None:
            creator = await session.get(Creator, creator_id)
        else:
            result = await session.execute(select(Creator).where(Creator.name == name).limit(2))
            matches = result.scalars().all()
            if len(matches) > 1:
                print(f'Multiple creators found with name "{name}". Use --creator-id instead.')
                sys.exit(1)
            creator = matches[0] if matches else None

        if not creator:
            print("Creator not found")
            sys.exit(1)

        creator.password_hash = hash_pin(pin)
        await session.commit()
        print(f"PIN reset for creator #{creator.id} ({creator.name})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a creator's PIN")
    identifier = parser.add_mutually_exclusive_group(required=True)
    identifier.add_argument("--creator-id", type=int)
    identifier.add_argument("--name")
    parser.add_argument("--pin", required=True)
    args = parser.parse_args()

    asyncio.run(_reset(creator_id=args.creator_id, name=args.name, pin=args.pin))


if __name__ == "__main__":
    main()
