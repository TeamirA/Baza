"""Vercel build step (the buildCommand in vercel.json).

Runs after dependencies are installed. Vercel runs collectstatic on its own.
- Applies migrations when DATABASE_URL is set (the Postgres integration sets it).
- Seeds sample products when SEED_PRODUCTS=1 (idempotent).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    import django
    from django.core.management import call_command

    django.setup()

    if not os.environ.get("DATABASE_URL"):
        print("vercel_build: DATABASE_URL not set, skipping migrations.")
        return

    print("vercel_build: applying migrations...")
    call_command("migrate", interactive=False)

    if os.environ.get("SEED_PRODUCTS") == "1":
        print("vercel_build: seeding sample products...")
        call_command("seed_products")


if __name__ == "__main__":
    main()
