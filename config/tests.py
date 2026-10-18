import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

_spec = importlib.util.spec_from_file_location(
    "vercel_build", Path(__file__).resolve().parent.parent / "scripts" / "vercel_build.py"
)
vercel_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vercel_build)

DB = {"DATABASE_URL": "postgres://example"}


class VercelBuildMigrationGuardTests(SimpleTestCase):
    def check(self, **env):
        return vercel_build.should_migrate(env)[0]

    def test_production_migrates(self):
        self.assertTrue(self.check(VERCEL_ENV="production", **DB))

    def test_preview_never_migrates_by_default(self):
        # Without Neon preview branching, previews share the production database.
        self.assertFalse(self.check(VERCEL_ENV="preview", **DB))

    def test_preview_migrates_only_when_opted_in(self):
        self.assertTrue(self.check(VERCEL_ENV="preview", PREVIEW_MIGRATIONS="1", **DB))
        self.assertFalse(self.check(VERCEL_ENV="preview", PREVIEW_MIGRATIONS="true", **DB))

    def test_nothing_without_a_database_or_outside_vercel(self):
        self.assertFalse(self.check(VERCEL_ENV="production"))
        self.assertFalse(self.check(**DB))
