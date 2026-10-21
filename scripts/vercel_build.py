"""Vercel build step (the buildCommand in vercel.json).

Runs after dependencies are installed. Vercel runs collectstatic on its own.

- Production builds apply migrations when DATABASE_URL is set (the Postgres
  integration sets it) and, when SEED_PRODUCTS=1, load the demo catalog
  (real products with photos, uploaded to Blob). Seeding only fills what's
  missing, so leaving the flag on is harmless.
- Preview builds only migrate when PREVIEW_MIGRATIONS=1. Without Neon preview
  branching, preview deployments share the production database, so a branch
  push must never change its schema. Turn the flag on (Preview environment
  only) once each preview gets its own Neon branch.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def should_migrate(env):
    vercel_env = env.get("VERCEL_ENV", "")
    if not env.get("DATABASE_URL"):
        return False, "DATABASE_URL not set"
    if vercel_env == "production":
        return True, "production build"
    if vercel_env == "preview" and env.get("PREVIEW_MIGRATIONS") == "1":
        return True, "preview build with PREVIEW_MIGRATIONS=1"
    return False, f"{vercel_env or 'non-Vercel'} build; set PREVIEW_MIGRATIONS=1 once previews have their own database"


def main():
    import django
    from django.core.management import call_command

    django.setup()

    migrate, reason = should_migrate(os.environ)
    if not migrate:
        print(f"vercel_build: skipping migrations ({reason}).")
        return

    print(f"vercel_build: applying migrations ({reason})...")
    call_command("migrate", interactive=False)

    if os.environ.get("SEED_PRODUCTS") == "1":
        print("vercel_build: seeding the demo catalog...")
        call_command("seed_products")


if __name__ == "__main__":
    main()
