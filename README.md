# Baza

A small e-commerce store built with Django: product catalog, session cart,
accounts, checkout with Stripe (test mode), and order history.

**Live demo: https://baza-market.vercel.app**

## Try it

1. **Browse** about 180 products across 9 categories. Filter by price or stock,
   sort, or search from the header. Typos are fine: try `iphnoe` or `lapotp`.
2. **Sign up** (or check out as a guest), save a few items with the ♥, and add
   some to your cart.
3. **Check out** and pay with Stripe's test card `4242 4242 4242 4242`, any future
   expiry date and any CVC. It's test mode, so no real money moves.
4. **After paying**, open the order to see its timeline and "Buy again", review a
   product you bought, and manage saved addresses under **Account**.

Works on phones too, with light and dark themes (toggle in the header).

## How it's built

- **Backend:** Django 4.2. Each domain is its own app (`products`, `orders`, `users`, `payments`),
  and each app is split into models → repositories (ORM only) → services → views.
- **Frontend:** server-rendered templates, plain CSS/JS, and reusable
  [django-components](https://github.com/django-components/django-components) widgets.
- **Database:** SQLite locally, Postgres (Neon via Vercel) in production.
- **Payments:** a `PaymentGateway` interface with a Stripe implementation (`payments/gateways/`).
- **Search and browsing:** relevance-ranked, typo-tolerant search (`products/search.py`)
  with live suggestions and recent searches in the header, plus price and stock filters,
  sorting, pagination and a "Recently viewed" row.
- **Accounts:** a wishlist ("Saved"), reviews from verified buyers, an order timeline
  with tracking numbers and "Buy again", and an account page (`/accounts/profile/`) with
  saved shipping addresses (picked at checkout), email change and password change.

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

**Demo catalog.** `seed_products` loads about 180 real products (phones, laptops,
kitchenware, groceries, beauty, fashion, watches...) with brands, prices, stock,
warranty/shipping/returns details and up to three photos each, from
`products/data/catalog.json`. The data and photos come from
[DummyJSON](https://dummyjson.com), a free product dataset for demo stores; photos
are downloaded when seeding (a few minutes), put on white and saved as WebP. Running
it again only fills in photos that failed to download. `--no-photos` skips them.

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
   | `SEED_PRODUCTS` | `1` to load the demo catalog on the next deploy (optional; remove it afterwards so products you delete stay deleted) |
   | `CRON_SECRET` | a long random string; Vercel Cron sends it to `/cron/expire-unpaid-orders/` |
   | `ORDER_HOLD_HOURS` | optional, default `24`: how long unpaid orders hold their stock |
   | `SITE_URL` | `https://baza-market.vercel.app`, used for links in emails |
   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP details from your email provider (optional; see below) |
   | `DEFAULT_FROM_EMAIL` | e.g. `Baza <orders@yourdomain.com>` |
   | `SENTRY_DSN` | optional: your Sentry project's DSN, to get error reports (no personal data is sent) |
   | `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | only if you add a custom domain |
4. **Redeploy.** Production builds run migrations.

   **Preview deployments** don't migrate by default, because without Neon preview
   branching they'd share the production database. To give each preview its own
   copy, go to Storage → your Neon database → Projects → baza and enable
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

**Product photos:** upload them in the admin, on each product's page (Photos
section). Each photo is resized to 400/800/1600px WebP versions; the first photo
(lowest position) is the cover, and the second shows when hovering a product
card. In production files go to Vercel Blob. Create a **public** Blob store and
connect it to the project, which sets `BLOB_READ_WRITE_TOKEN`. Locally, without
that token, files are saved to `media/` (gitignored). Uploads must be under 4 MB
(a Vercel limit on request size).

**Email:** order confirmations, "your order has shipped" (sent when you set
an order to Shipped in the admin), and password reset all use SMTP. With
Resend, for example, use `EMAIL_HOST=smtp.resend.com`, `EMAIL_HOST_USER=resend`
and your API key as `EMAIL_HOST_PASSWORD`, and verify your sending domain.
Without `EMAIL_HOST`, emails print to the console locally, are skipped in
production, and the "Forgot password?" link is hidden.

**Unpaid orders:** checkout reserves stock right away. A daily Vercel Cron
(`vercel.json`) cancels orders still unpaid after `ORDER_HOLD_HOURS` and puts their
stock back; Stripe payment pages expire after 23 hours to match. You can run it by
hand with `python manage.py expire_unpaid_orders`, or use the "Cancel selected
unpaid orders" admin action. Shoppers can also cancel unpaid orders themselves.

Test card: `4242 4242 4242 4242`, with any future expiry date and any CVC.

**Promo codes:** create a coupon and a promotion code in the Stripe Dashboard
(Product catalog → Coupons). Shoppers can enter the code on Stripe's payment page,
and the order records what they actually paid.
