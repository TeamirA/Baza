# Project Handoff Brief: Django E-Commerce MVP → Vercel

---

## 🎯 Project Goal

Build a **minimum viable e-commerce site** with the following MVP features:
- Product listings + product detail pages
- Shopping cart
- User registration / login
- Order processing with **Stripe** payment integration
- Admin panel via Django admin for product/order management

**Deploy final result to Vercel** with a **PostgreSQL** database provisioned through Vercel's storage.

---

## 🧱 Tech Stack (Locked In)

| Layer | Choice |
|---|---|
| Backend | **Django** (Python) — chosen for batteries-included admin, ORM, and auth |
| Frontend | Server-rendered Django templates + vanilla HTML/CSS/JS |
| UI Components | **`django-components`** (self-contained HTML/CSS/JS widgets) |
| Database | **PostgreSQL** (via Vercel Marketplace / Neon) |
| Payments | **Stripe** (test mode for MVP), behind an abstraction layer for future gateway swaps |
| Static files | **WhiteNoise** |
| Env config | `python-dotenv` locally, Vercel env vars in prod |
| Hosting | **Vercel** (Python serverless runtime) |
| Dev OS | **macOS** — all commands must use `python3` before venv activation |

**Packages installed (`requirements.txt`):**
django
psycopg2-binary
whitenoise
dj-database-url
python-dotenv
stripe
django-components

---

## 🏗 Architecture Rules (NON-NEGOTIABLE)

1. **Layered separation per app:**
   - `models.py` → Django ORM entities only
   - `repositories.py` → **only** layer allowed to touch the ORM
   - `services.py` → business logic / use cases
   - `dtos.py` → data transfer objects
   - `views.py` → thin presentation layer, no business logic
2. **Reusable UI widgets** — every UI element that repeats (product cards, error cards, buttons, forms) must be a `django-components` component in `components/<name>/` with its own `.py`, `.html`, `.css`.
3. **Visible error handling** — every view must catch exceptions and pass an `error` context var; templates render it via the reusable `error_card` component. Forms use Django's `form.errors`.
4. **Payment gateway abstraction** — an interface (`PaymentGateway` ABC) with a `StripeGateway` implementation, so future gateways (PayPal, Razorpay) can be added without touching views.
5. **Micro-service-style modularity** — one Django app per domain (`products`, `orders`, `users`, `payments`).

---

## ✅ What Is Already Done (Phase 1, Steps 1–4)

- Project folder `ecommerce-mvp/` with `.venv/` activated
- Django project created: `config/` (settings, urls, wsgi, asgi)
- Four apps created: `products`, `orders`, `users`, `payments`
- Clean-architecture subfolders scaffolded inside each app (`components/`, empty `services.py`, `repositories.py`, `dtos.py`)
- `config/settings.py` configured with:
  - `dj_database_url` reading `DATABASE_URL` (falls back to SQLite locally)
  - `whitenoise.middleware.WhiteNoiseMiddleware` added after `SecurityMiddleware`
  - `django_components` in `INSTALLED_APPS`
  - Stripe env vars (`STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`)
  - `ALLOWED_HOSTS` includes `127.0.0.1` and `.vercel.app`
  - Static files: `STATIC_URL='/static/'`, `STATIC_ROOT=BASE_DIR/'staticfiles'`, WhiteNoise compressed storage
- `config/wsgi.py` exposes `app = application` for Vercel
- `WSGI_APPLICATION = 'config.wsgi.app'`
- `vercel.json` in project root with the Python build + catch-all route

---

## 🚧 What Remains (Steps 5 → 15)

### Step 5 — Models
- `products/models.py`: `Product` (name, slug, description, price Decimal, image, stock, is_active)
- `orders/models.py`: `Order` (user FK, status choices `pending/paid/shipped/cancelled`, created_at, stripe_session_id) and `OrderItem` (order FK related_name='items', product FK, quantity, price snapshot)
- `users`: use Django's built-in `User`; add a registration view + template (no custom user model for MVP)

### Step 6 — Repositories & Services
- `ProductRepository`: `get_all_active()`, `get_by_slug(slug)`, `get_by_id(id)`
- `OrderService.create_order(user, cart_items)` and `OrderService.mark_as_paid(order, stripe_session_id=None)`

### Step 7 — `django-components` widgets
- `products/components/product_card/` (py + html + css)
- A global `components/error_card/` (py + html + css) — reused in **every** template
- Register via `@register("component_name")` and use `{% component "..." param=val %}{% endcomponent %}`

### Step 8 — Views, URLs, Templates
- `product_list`, `product_detail` (with `DoesNotExist` → `error` context)
- Cart views (session-based cart is fine for MVP)
- Auth: `django.contrib.auth.urls` for login/logout + custom registration view in `users/`
- Templates under each app's `templates/<app>/`

### Step 9 — Payment abstraction
- `payments/gateways/base.py`: `PaymentGateway(ABC)` with `create_checkout_session()` and `verify_webhook()`
- `payments/gateways/stripe_gateway.py`: `StripeGateway` implementation using `stripe.checkout.Session.create(...)` with `client_reference_id=order.id`

### Step 10 — Checkout + Webhook
- `payments/views.py`: `checkout(request, order_id)` redirects to Stripe; `stripe_webhook` (csrf_exempt) handles `checkout.session.completed` → `OrderService.mark_as_paid()`
- Register webhook URL in Stripe dashboard → `https://<app>.vercel.app/payments/webhook/`

### Steps 11–15 — Deployment
- Provision Postgres via Vercel Dashboard → Storage
- Add env vars on Vercel: `SECRET_KEY`, `DEBUG=False`, `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (Vercel auto-adds `DATABASE_URL`)
- Run `python manage.py makemigrations && migrate && collectstatic`
- `npm i -g vercel` → `vercel --prod`

---

## 💻 Mac-Specific Command Rules (Critical)

- ❌ `python -m venv .venv` → ✅ `python3 -m venv .venv`
- ❌ `python ...` before venv activation → ✅ `python3 ...`
- ❌ `pip ...` before venv activation → ✅ `pip3 ...`
- ✅ `source .venv/bin/activate` (after this, `python`/`pip` work normally)

If `psycopg2-binary` fails: `brew install postgresql` then reinstall. Never use bare `psycopg2`.

---

## 🎨 Error-Handling Pattern (Apply Everywhere)

Python (in every view):
    try:
        ...
    except SomeError as e:
        return render(request, 'template.html', {'error': f'Human-readable: {e}'})

Template (in every template):
    {% if error %}{% component "error_card" message=error %}{% endcomponent %}{% endif %}

---

## 📁 Expected Final File Tree (Abridged)

ecommerce-mvp/
├── .venv/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py            # exposes `app`
├── products/
│   ├── models.py repositories.py services.py views.py urls.py admin.py
│   ├── components/product_card/{product_card.py,.html,.css}
│   └── templates/products/
├── orders/
│   ├── models.py services.py repositories.py views.py urls.py admin.py
│   └── templates/orders/
├── users/
│   ├── views.py urls.py
│   └── templates/users/
├── payments/
│   ├── gateways/{base.py,stripe_gateway.py}
│   ├── views.py urls.py
│   └── templates/payments/
├── components/error_card/{error_card.py,.html,.css}
├── templates/base.html
├── requirements.txt
├── vercel.json
└── manage.py

---

## 🧭 Development guidelines

The user has completed Phase 1 (Steps 1–4). **Do not re-scaffold the project or reinstall packages.** Continue from **Step 5** onward.

- Follow the clean-architecture layering strictly: ORM only in `repositories.py`, business logic only in `services.py`, views stay thin.
- Every UI element that repeats must be a `django-components` component in its own folder.
- Every view must surface errors visibly via the reusable `error_card` component.
- Payment code must go through the `PaymentGateway` abstraction — no direct `stripe.*` calls in views or services.
- All shell commands must be macOS-compatible (`python3`, `source .venv/bin/activate`).
- Target deployment: Vercel + PostgreSQL (Vercel Storage) + Stripe test mode.
- Ask the user for confirmation **only if** something in this brief is ambiguous — otherwise proceed step by step and wait for "done" between steps.

---

**Deliver step-by-step instructions starting at Step 5, one step per message, waiting for the user's confirmation before moving to the next.**
