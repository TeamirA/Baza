# Corner Store

A small e-commerce store built with Django: product catalog, session cart,
accounts, checkout with Stripe (test mode), and order history.

- **Backend:** Django 4.2. Each domain is its own app (`products`, `orders`, `users`, `payments`),
  and each app is split into models → repositories (ORM only) → services → views.
- **Frontend:** server-rendered templates, plain CSS/JS, and reusable
  [django-components](https://github.com/django-components/django-components) widgets.
- **Database:** SQLite locally, Postgres (Neon via Vercel) in production.
- **Payments:** a `PaymentGateway` interface with a Stripe implementation (`payments/gateways/`).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_products
python manage.py createsuperuser
python manage.py runserver
```

Then open http://127.0.0.1:8000. The admin is at `/admin/`.

Without Stripe keys, and only with `DEBUG=True`, checkout uses a dev gateway that
marks orders paid straight away, so you can try the whole flow. To use real Stripe test
mode locally, set the `STRIPE_*` keys in `.env` and forward webhooks:

```bash
stripe listen --forward-to localhost:8000/payments/webhook/
```

Run the tests:

```bash
python manage.py test
```

## Deploy to Vercel

Vercel detects the project as Django from `manage.py`. During the build it installs
`requirements.txt`, runs `scripts/vercel_build.py` (the `buildCommand` in `vercel.json`: migrations, plus optional seeding),
and then runs `collectstatic`, which serves `/static/` from the CDN.

1. **Import the repo** into Vercel (framework preset: Django).
2. **Add Postgres:** Project → Storage → Create → Neon. This sets `DATABASE_URL`.
3. **Set environment variables** (Production and Preview):
   | Name | Value |
   |---|---|
   | `SECRET_KEY` | a long random string |
   | `STRIPE_PUBLIC_KEY` | `pk_test_...` |
   | `STRIPE_SECRET_KEY` | `sk_test_...` |
   | `STRIPE_WEBHOOK_SECRET` | `whsec_...` (from step 5) |
   | `SEED_PRODUCTS` | `1` for the first deploy if you want sample products (optional) |
   | `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | only if you add a custom domain |
4. **Redeploy.** Production builds run migrations.

   **Preview deployments** don't migrate by default, because without Neon preview
   branching they'd share the production database. To give each preview its own
   copy, go to Storage → your Neon database → Projects → corner-store and enable
   **Preview** under *Deployments Configuration*, along with *Resource must be
   active before deployment*. Then add `PREVIEW_MIGRATIONS=1` for the **Preview**
   environment only.
5. **Stripe webhook:** in the Stripe Dashboard (test mode), go to Developers → Webhooks → Add endpoint:
   - URL: `https://<your-app>.vercel.app/payments/webhook/`
   - Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`

   Copy the signing secret into `STRIPE_WEBHOOK_SECRET`, then redeploy.
6. **Create an admin user** against the production database:
   ```bash
   vercel env pull .env.local
   python manage.py createsuperuser
   ```
   (`.env.local` is gitignored. Delete it afterwards if you don't need it.)

Test card: `4242 4242 4242 4242`, with any future expiry date and any CVC.

**Promo codes:** create a coupon and a promotion code in the Stripe Dashboard
(Product catalog → Coupons). Shoppers can enter the code on Stripe's payment page,
and the order records what they actually paid.
