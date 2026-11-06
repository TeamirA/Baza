# Baza

Baza is an online store built with Django. Shoppers can browse and search a catalog
of real products, keep a cart, create an account, pay with Stripe (test mode) and
follow their orders. Staff run the store from the Django admin.

**Live demo: https://baza-market.vercel.app**

Built for the CodeAlpha "Simple E-commerce Store" task: product listings, a
shopping cart, order processing, user registration/login, and a database for
products, users and orders.

## Contents

- [Features](#features)
- [How to use the store (shoppers)](#how-to-use-the-store-shoppers)
- [How to run the store (admins)](#how-to-run-the-store-admins)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Data model](#data-model)
- [Pages and URLs](#pages-and-urls)
- [Run it locally](#run-it-locally)
- [Configuration](#configuration)
- [Management commands](#management-commands)
- [Tests](#tests)
- [Deploy to Vercel](#deploy-to-vercel)
- [Credits](#credits)

## Features

**Catalog**
- About 180 real products in 9 categories (Electronics, Kitchen, Fashion,
  Groceries, Sports, Watches & Jewellery, Beauty, Home, Accessories). Each has a
  brand, SKU, price, stock, warranty/shipping/returns details and up to three photos.
- Product pages with a photo gallery, stock status, details, reviews and
  "More in this category" suggestions.
- Filters (category, price range, in stock only), sorting (best match, newest,
  price, name) and pagination.
- A "Recently viewed" row, remembered per browser.

**Search**
- Search box in the header with live suggestions and your recent searches.
- Results ranked by relevance (name, then category, then description).
- Tolerates typos: `iphnoe` finds iPhones and `lapotp` finds laptops, with a
  "Showing results for…" note.

**Cart and checkout**
- Guests' carts live in the session. Signed-in users' carts are saved in the
  database, so they follow them across devices. A guest cart is merged into the
  account at login.
- Quantity steppers, live totals and stock checks, so nobody can add more than is in stock.
- Checkout as a guest or with an account. Signed-in users can pick a saved address,
  and can save a new address during checkout.
- Payment on Stripe's hosted page (test mode). Promo codes created in Stripe are
  accepted, and the order records the amount actually paid.

**Orders**
- Stock is reserved when the order is placed. Orders still unpaid after 24 hours
  (configurable) are cancelled automatically and their stock goes back on sale.
- Order history with a status timeline (placed → paid → shipped), tracking number,
  **Cancel** for unpaid orders and **Buy again**.
- Guests get a private tracking link for their order.
- Emails: order confirmation, "your order has shipped" and password reset (when SMTP
  is configured).

**Accounts**
- Register, log in, log out, change password, reset a forgotten password.
- Account page: change email, manage saved shipping addresses, set a default one.
- Wishlist ("Saved", the ♥ button) with **Move to cart**.
- 1–5 star reviews from customers who bought the product, marked "Verified
  purchase". The demo catalog's reviews are marked "Sample review".

**Interface**
- Responsive layout for phones, tablets and desktops.
- Light and dark themes (toggle in the header; follows the system setting by default).
- Toast messages, accessible forms and a keyboard-friendly star picker.
- Branded 404 and 500 pages; a missing product page suggests searching for it.
- A slim bar at the top tells visitors it's a demo store and which test card to use.

**Admin**
- Manage categories, products (with photo uploads), orders, reviews and addresses.
- Mark an order as shipped, with a tracking number, to email the customer.
- Bulk action to cancel unpaid orders.

## How to use the store (shoppers)

Open https://baza-market.vercel.app (or http://127.0.0.1:8000 when running locally).

1. **Find a product.** Browse the home page, pick a category, or type in the search
   box at the top. Narrow the list by price or stock with the filters, and reorder it
   with **Sort by**.
2. **Look closer.** Click a product to see its photos, price, stock, details and reviews.
   Click **♥** to save it for later (you'll be asked to log in first).
3. **Add to cart.** Pick a quantity and click **Add to cart**. The **Cart** link in the
   header shows how many items you have.
4. **Review the cart.** Open **Cart** to change quantities or remove items. The total
   updates as you go.
5. **Check out.** Click **Checkout**, enter your name, email and shipping address (or
   pick a saved address), then click **Place order & pay**.
6. **Pay.** On Stripe's page use the test card:
   - Card number: `4242 4242 4242 4242`
   - Expiry: any future date, e.g. `12/34`
   - CVC: any 3 digits, e.g. `123`

   No real money is charged. If you go back from Stripe's page instead, the order
   stays unpaid and you can pay for it later from the order page.
7. **Follow your order.** After paying you land on a confirmation page. Signed-in
   users find every order under **Orders**, with its status timeline, tracking number
   (once shipped) and **Buy again**. Guests use the tracking link from the
   confirmation page and email.
8. **Review what you bought.** On the product page, pick a star rating, add a title
   and comment, and submit.

**Your account**

- **Sign up:** click **Sign up** in the header and choose a username, email and password.
- **Log in / out:** **Log in** and **Log out** are in the header.
- **Account** (`/accounts/profile/`): change your email or password, and add, delete
  or set a default shipping address.
- **Forgot password:** use the link on the login page (shown when email is configured).
- **Saved:** lists your ♥ items, with **Move to cart**.
- **Theme:** the button in the header switches between light and dark mode.

## How to run the store (admins)

Staff accounts see an **Admin** link in the header, or go to `/admin/` directly.
Create the first one with `createsuperuser` (see [Run it locally](#run-it-locally)).

- **Add a category:** Categories → Add. The URL slug fills itself in.
- **Add a product:** Products → Add. Fill in name, category, price, stock and
  description, and optionally brand, SKU and details (label/value rows such as
  "Warranty"). Save, then upload photos in the **Photos** section. The first photo is
  the cover and the second shows when hovering over a product card.
- **Hide a product:** untick **Is active**. Hidden products still show in past orders.
- **Process an order:** Orders → open the order. When it's sent, set the status to
  **Shipped** and add a tracking number; the customer gets an email.
- **Cancel unpaid orders:** select them in the list and run **Cancel selected unpaid
  orders**. Their stock goes back on sale.
- **Moderate reviews:** Reviews → filter by rating or by sample/real, and delete any
  that break the rules.

## Tech stack

| Part | Choice |
|---|---|
| Language | Python 3.12 (3.9 or newer works) |
| Web framework | Django 4.2 |
| UI components | [django-components](https://github.com/django-components/django-components) 0.146 |
| Frontend | Server-rendered HTML templates, plain CSS and JavaScript (no build step) |
| Database | SQLite locally, PostgreSQL (Neon) in production |
| Payments | Stripe Checkout (test mode), behind a `PaymentGateway` interface |
| Images | Pillow, resized to WebP; stored in Vercel Blob in production, `media/` locally |
| Static files | WhiteNoise and the Vercel CDN |
| Hosting | Vercel (Python runtime) with a daily Vercel Cron job |
| Monitoring | Sentry (optional) |

## Architecture

Each part of the store is its own Django app, and every app uses the same layers:

```
request → view → service → repository → model / database
                    ↓
                   DTO → template + components → HTML
```

- **Models** (`models.py`) define the tables.
- **Repositories** (`repositories.py`) are the only code that queries the database.
- **Services** (`services.py`) hold the business rules (stock reservation, pricing,
  who may review, default addresses…) and return plain data objects (`dtos.py`).
- **Views** (`views.py`) stay thin: read the request, call a service, render a template.
- **Components** (`components/` and each app's `components/`) are reusable UI pieces
  (search box, quantity stepper, star rating, toast, pagination, theme toggle…), each
  with its own HTML, CSS and JS.

Other building blocks:

- **Payments:** `payments/gateways/` has a `PaymentGateway` base class, a Stripe
  implementation and a dev gateway for local use. Stripe payments are confirmed both
  by the return page and by the webhook; both paths are idempotent, so an order is
  never marked paid twice.
- **Media storage:** `config/media_store.py` saves photos to Vercel Blob or the local disk.
- **Search:** `products/search.py` scores matches and corrects typos against the
  catalog's own words.
- **Middleware:** `config/middleware.py` redirects the store's old domain to the current one.

## Project structure

```
.
├── config/          Settings, URLs, middleware, media storage, Sentry setup
├── products/        Catalog, search, photos, wishlist, reviews, seed command
│   └── data/        catalog.json (demo products and sample reviews)
├── orders/          Cart, checkout, orders, emails, unpaid-order cleanup
├── payments/        Payment gateways (Stripe, dev) and pay/success/cancel/webhook views
├── users/           Registration, account page, saved addresses
├── components/      Shared UI components (django-components)
├── templates/       Base layout, 404/500 pages, login and password pages
├── static/          main.css and page scripts (cart, checkout, filters, forms)
├── scripts/         vercel_build.py (migrations and seeding during deploys)
├── docs/            Project notes
├── manage.py
├── requirements.txt
└── vercel.json      Build command, cron schedule, function settings
```

Each app also has its own `templates/`, `migrations/` and `tests/` folders.

## Data model

| Model | App | What it stores |
|---|---|---|
| `Category` | products | Name and slug |
| `Product` | products | Name, slug, brand, SKU, category, description, details, price, stock, active flag |
| `ProductImage` | products | Photo sizes (400/800/1600 px WebP), dimensions, alt text, position |
| `Review` | products | Product, author, rating 1–5, title, comment |
| `SavedProduct` | products | A user's wishlist entry |
| `CartItem` | orders | A signed-in user's cart line (guests use the session) |
| `Order` | orders | Customer, status (pending / paid / shipped / cancelled), shipping details, Stripe session, amount paid, tracking number, timestamps |
| `OrderItem` | orders | Product, quantity and the price at the time of purchase |
| `Address` | users | A user's saved shipping address, and whether it's the default |
| `User` | Django auth | Username, email, hashed password |

## Pages and URLs

| URL | Page |
|---|---|
| `/` | Product list with search, filters and sorting |
| `/products/<slug>/` | Product page |
| `/saved/` | Wishlist |
| `/cart/` | Cart |
| `/checkout/` | Checkout |
| `/orders/` | Order history (signed in) |
| `/orders/<id>/` | Order details |
| `/orders/track/<token>/` | Private order tracking link (works for guests) |
| `/payments/success/` | Payment confirmation |
| `/payments/webhook/` | Stripe webhook (POST only) |
| `/accounts/register/` | Sign up |
| `/accounts/login/`, `/accounts/logout/` | Log in, log out |
| `/accounts/profile/` | Account page |
| `/accounts/password_change/`, `/accounts/password_reset/` | Change or reset password |
| `/admin/` | Django admin |
| `/cron/expire-unpaid-orders/` | Daily cleanup, called by Vercel Cron (needs `CRON_SECRET`) |

## Run it locally

You need Python 3.9 or newer and git.

```bash
git clone https://github.com/TeamirA/Baza.git
cd Baza
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python manage.py migrate
python manage.py seed_products     # demo catalog; downloads photos (a few minutes)
python manage.py createsuperuser   # your admin account
python manage.py runserver
```

Open http://127.0.0.1:8000 for the store and http://127.0.0.1:8000/admin/ for the admin.

- `python manage.py seed_products --no-photos` loads the products without photos in
  a few seconds.
- **Payments:** with no Stripe keys in `.env` and `DEBUG=True`, a dev gateway marks
  orders as paid straight away, so you can try the whole flow. To use Stripe test
  mode instead, put your test keys in `.env` and forward webhooks with the
  [Stripe CLI](https://stripe.com/docs/stripe-cli):

  ```bash
  stripe listen --forward-to localhost:8000/payments/webhook/
  ```
- **Emails** print to the terminal running the server.

## Configuration

Settings come from environment variables: `.env` locally (see `.env.example`), the
project's Environment Variables on Vercel.

| Variable | Needed | Purpose |
|---|---|---|
| `SECRET_KEY` | always | Django secret key, a long random string |
| `DEBUG` | locally | `True` locally; leave unset in production |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | custom domain | Vercel domains are allowed automatically |
| `DATABASE_URL` | production | Postgres connection; SQLite is used when unset |
| `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY` | production | Stripe test keys (`pk_test_…`, `sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | production | Signing secret of the Stripe webhook (`whsec_…`) |
| `BLOB_READ_WRITE_TOKEN` | production | Vercel Blob store for photos (set when you connect the store) |
| `CRON_SECRET` | production | Protects the daily cleanup URL; Vercel Cron sends it |
| `SITE_URL` | recommended | Public address, used for links in emails |
| `ORDER_HOLD_HOURS` | optional | Hours an unpaid order holds its stock (default 24) |
| `SEED_PRODUCTS` | optional | `1` loads the demo catalog during deploys |
| `STORE_NAME` | optional | Store name in the header and emails (default `Baza`) |
| `DEMO_NOTICE` | optional | `0` hides the demo-store bar |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | optional | SMTP for emails |
| `SENTRY_DSN` | optional | Send error reports to Sentry |
| `PREVIEW_MIGRATIONS` | optional | `1` lets preview deployments migrate (only with their own database) |

## Management commands

| Command | What it does |
|---|---|
| `python manage.py seed_products` | Loads the demo catalog: products, photos and sample reviews. Safe to run again; it only fills in what's missing. `--no-photos` skips photos; `--workers N` sets how many products download in parallel. |
| `python manage.py expire_unpaid_orders` | Cancels orders unpaid for longer than `ORDER_HOLD_HOURS` and returns their stock. |
| `python manage.py createsuperuser` | Creates an admin account. |

## Tests

177 automated tests cover the catalog, search, photos, wishlist, reviews, cart,
checkout, payments (with a fake gateway), order timeline, accounts, settings and
the seed command.

```bash
python manage.py test
```

## Deploy to Vercel

Vercel detects the project as Django from `manage.py`. Each deploy installs
`requirements.txt`, runs `scripts/vercel_build.py` (migrations on production builds,
plus the demo catalog when `SEED_PRODUCTS=1`) and collects static files.

1. **Import the repo** into Vercel (framework preset: Django).
2. **Add Postgres:** Storage → Create → Neon. This sets `DATABASE_URL`.
3. **Add a public Blob store:** Storage → Create → Blob, and connect it to the
   project. This sets `BLOB_READ_WRITE_TOKEN`.
4. **Set the environment variables** from [Configuration](#configuration): at least
   `SECRET_KEY`, the three `STRIPE_*` keys, `CRON_SECRET` and `SITE_URL`. Add
   `SEED_PRODUCTS=1` if you want the demo catalog.
5. **Deploy.** Production builds run the migrations.
6. **Stripe webhook:** in the Stripe Dashboard (test mode), open Developers →
   Webhooks → Add endpoint.
   - URL: `https://<your-app>.vercel.app/payments/webhook/`
   - Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`

   Put its signing secret in `STRIPE_WEBHOOK_SECRET` and redeploy.
7. **Create an admin** against the production database:
   ```bash
   vercel env pull .env.local
   python manage.py createsuperuser
   ```
   `.env.local` is gitignored; delete it when you're done.

Notes:

- **Preview deployments** share the production database unless Neon preview
  branching is on, so they don't migrate. To give each preview its own database,
  enable **Preview** in the Neon integration's deployment settings and set
  `PREVIEW_MIGRATIONS=1` for the Preview environment only.
- **Photo uploads** must be under 4 MB (Vercel's request size limit).
- **Email:** with Resend, for example, use `EMAIL_HOST=smtp.resend.com`,
  `EMAIL_HOST_USER=resend` and your API key as `EMAIL_HOST_PASSWORD`. Without
  `EMAIL_HOST`, production skips emails and hides "Forgot password?".
- **Unpaid orders:** a Vercel Cron job runs the cleanup daily at 03:00 UTC (see
  `vercel.json`). Stripe payment pages expire after 23 hours, within the 24-hour hold.

## Credits

- Built by [TeamirA](https://github.com/TeamirA) for the CodeAlpha internship.
- Demo products, photos and sample reviews come from [DummyJSON](https://dummyjson.com),
  a free dataset for demo stores.
