"""Error monitoring. Off unless SENTRY_DSN is set (Vercel: Production env var)."""


def init_sentry(env):
    dsn = env.get("SENTRY_DSN", "")
    if not dsn:
        return False

    # Imported here so local runs without a DSN don't load the SDK at all.
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=env.get("VERCEL_ENV", "development"),
        release=env.get("VERCEL_GIT_COMMIT_SHA") or None,
        # Performance tracing is opt-in; errors are always reported.
        traces_sample_rate=float(env.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        # Don't send cookies, IPs, or user details (shoppers' personal data).
        send_default_pii=False,
    )
    return True
