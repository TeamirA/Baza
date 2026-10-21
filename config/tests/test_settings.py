import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

_spec = importlib.util.spec_from_file_location(
    "vercel_build", Path(__file__).resolve().parents[2] / "scripts" / "vercel_build.py"
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


from unittest import mock

from config.sentry import init_sentry


class SentryInitTests(SimpleTestCase):
    def test_off_without_dsn(self):
        with mock.patch("sentry_sdk.init") as init:
            self.assertFalse(init_sentry({}))
        init.assert_not_called()

    def test_on_with_dsn_and_no_personal_data(self):
        env = {"SENTRY_DSN": "https://key@o0.ingest.sentry.io/0", "VERCEL_ENV": "production", "VERCEL_GIT_COMMIT_SHA": "abc123"}
        with mock.patch("sentry_sdk.init") as init:
            self.assertTrue(init_sentry(env))
        kwargs = init.call_args.kwargs
        self.assertEqual(kwargs["environment"], "production")
        self.assertEqual(kwargs["release"], "abc123")
        self.assertEqual(kwargs["traces_sample_rate"], 0.0)
        self.assertFalse(kwargs["send_default_pii"])


from django.test import TestCase, override_settings


@override_settings(
    SITE_URL="https://baza-market.vercel.app",
    LEGACY_HOSTS=["corner-store-omega.vercel.app"],
    ALLOWED_HOSTS=["baza-market.vercel.app", "corner-store-omega.vercel.app"],
)
class LegacyHostRedirectTests(TestCase):
    OLD = "corner-store-omega.vercel.app"

    def test_page_views_move_to_new_address(self):
        response = self.client.get("/search/suggest/?q=mug", HTTP_HOST=self.OLD)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://baza-market.vercel.app/search/suggest/?q=mug")

    def test_webhooks_and_cron_stay_put(self):
        self.assertNotEqual(self.client.post("/payments/webhook/", HTTP_HOST=self.OLD).status_code, 301)
        self.assertNotEqual(self.client.get("/cron/expire-unpaid-orders/", HTTP_HOST=self.OLD).status_code, 301)

    def test_new_address_is_served(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="baza-market.vercel.app").status_code, 200)
