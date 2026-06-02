# Inventory Management Dashboard

A production-ready inventory management system for small-to-medium businesses,
built with **Django**, **PostgreSQL**, **Tailwind CSS**, **Chart.js** and
**Django REST Framework**. It tracks products, stock movements, suppliers,
purchase orders, and produces dashboards and exportable reports — all behind a
role-based access control system.

> **Python / Django compatibility:** This project ships pinned for **Python 3.14**,
> which requires **Django 6.0** and **DRF 3.17** (earlier Django versions crash on
> Python 3.14 inside the template engine). On Python 3.12 / 3.13 you may instead pin
> Django 5.1 / DRF 3.15 — see the comments in [`requirements.txt`](requirements.txt).

---

## Table of Contents
1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Data Model / ER Diagram](#data-model--er-diagram)
6. [Roles & Permissions](#roles--permissions)
7. [Quick Start (Local)](#quick-start-local)
8. [Running with Docker](#running-with-docker)
9. [REST API](#rest-api)
10. [Reports & Exports](#reports--exports)
11. [Testing](#testing)
12. [Production Deployment (Ubuntu + Nginx + Gunicorn)](#production-deployment-ubuntu--nginx--gunicorn)
13. [Configuration Reference](#configuration-reference)

---

## Features

- **Authentication** — login, logout, password reset (email), password change, user profiles.
- **Role management** — 7 roles (Admin, Inventory Manager, Staff, Auditor, Production
  Planner, Floor Supervisor, Technician) with per-view and per-API enforcement.
- **Products & Categories** — full CRUD, SKU/barcode, pricing, search, filtering, pagination.
- **Suppliers** — full CRUD with contact and GST/VAT details.
- **Stock Transactions** — Stock In / Out / Adjustment that atomically update on-hand
  quantity and keep an immutable audit trail (`quantity_change`, `resulting_stock`).
- **Purchase Orders** — multi-line POs with a dynamic **"+ Add row"**, automatic totals,
  **partial receiving** (receive part of a line now, rest later), and a printable
  **Purchase Order / Invoice PDF**.
- **Production / Work Orders (SWO)** — Bill of Materials per product, stock **reservation**
  (`available = on-hand − reserved`), and a Planner → Supervisor → Technician lifecycle
  (release & reserve → assign → start → complete) that consumes components and produces
  finished goods automatically.
- **Dashboard** — KPI cards + Chart.js charts (monthly stock in/out, value trend,
  top-moving products) + low-stock and recent-activity panels.
- **Reports** — Inventory, Stock Movement, Low Stock, Purchase — with **quick date
  ranges** (7/15/30/90 days, month), a **movement-type** filter, a serial **No.** column,
  and **Excel / CSV / PDF** export that respects the active filters.
- **Audit / Activity Log** — every create/update/delete recorded with the acting user.
- **Global search** — one box searching products, suppliers, purchase orders and transactions.
- **Notifications** — reserved-aware low-stock alerts in the navbar bell, on every page.
- **REST API** — token/session-authenticated endpoints for every resource with
  pagination, filtering, search and ordering.
- **Tested** — 50+ automated tests, including an end-to-end QA suite (`inventory/tests_qa.py`).

---

## Tech Stack

| Layer        | Technology |
|--------------|------------|
| Language     | Python 3.12+ (tested on 3.14) |
| Framework    | Django 6.0 (Django 5.1 on Python ≤3.13) |
| API          | Django REST Framework 3.17 + django-filter |
| Database     | PostgreSQL 14+ via psycopg 3 (SQLite supported for quick trials) |
| UI           | Tailwind CSS 3 (Play CDN), Alpine.js, Bootstrap Icons, Chart.js 4 |
| Forms        | Plain Django forms styled with Tailwind partials (no Python UI deps) |
| Exports      | openpyxl (Excel), reportlab (PDF), csv (stdlib) |
| Static files | WhiteNoise |
| Server       | Gunicorn behind Nginx |

---

## Architecture

The project follows a **modular, app-per-domain** layout with a clean read/write split:

- **Models** own invariants. `Product.current_stock` is mutated *only* through
  `StockTransaction.save()` (which locks the row with `select_for_update`) and through
  `PurchaseOrder.receive_stock()`. This guarantees inventory and history never diverge.
- **Selectors** (`inventory/selectors.py`) hold read-side aggregation queries reused by
  the dashboard, API and reports — no duplicated ORM logic.
- **Datasets + exporters** (`reports/`) separate *what* a report contains from *how* it
  is rendered, so one dataset definition powers the HTML preview and all three export formats.
- **Permissions** are centralized in `accounts/permissions.py` (CBV mixins) and
  `api/permissions.py` (DRF permission classes).

```
Browser ──► Django views (HTML, Tailwind + Alpine.js templates)
   │                │
   │                ├── selectors ──► ORM ──► PostgreSQL
   │                └── datasets ──► exporters (xlsx / csv / pdf)
   └──► DRF API (token / session auth) ──► serializers ──► ORM
```

---

## Project Structure

```
inventory_management/
├── config/             # settings, root urls, wsgi/asgi
├── accounts/           # custom User + 7 roles, auth, profile, RBAC mixins
├── products/           # Category & Product (CRUD, search, filters, reserved/available)
├── suppliers/          # Supplier CRUD
├── inventory/          # StockTransaction, dashboard, global search, selectors, seed cmds, tests
├── purchases/          # PurchaseOrder + PurchaseItem, partial receiving, invoice PDF
├── production/         # Bill of Materials, WorkOrder (SWO) lifecycle, reservations
├── audit/              # ActivityLog + middleware/signals (who changed what)
├── reports/            # report datasets (date/type filters) + Excel/CSV/PDF exporters
├── api/                # DRF serializers, viewsets, routers, permissions
├── templates/          # base layout, partials, per-app pages, dashboard
├── static/             # app.css, app.js, vendored chart.js + alpine.js
├── media/              # uploaded product images / avatars
├── deploy/             # nginx.conf, gunicorn.service, bare-metal nginx
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
├── requirements.txt
├── .env.example
└── manage.py
```

---

## Data Model / ER Diagram

```
            ┌────────────┐         ┌──────────────┐
            │  Category  │1───────*│   Product    │
            └────────────┘         └──────┬───────┘
                                          │1
                          ┌───────────────┼───────────────┐
                          │*              │*               │*
                  ┌───────────────┐ ┌────────────┐ ┌───────────────┐
                  │StockTransaction│ │PurchaseItem│ │ (other refs)  │
                  └───────┬───────┘ └─────┬──────┘ └───────────────┘
                          │*              │*
                  ┌───────────────┐ ┌────────────────┐      ┌───────────┐
                  │     User      │ │ PurchaseOrder  │*────1│ Supplier  │
                  └───────────────┘ └────────────────┘      └───────────┘
                          │1
                  ┌───────────────┐
                  │    Profile    │
                  └───────────────┘
```

**Key relationships**
- `Product.category` → `Category` (PROTECT — categories with products can't be deleted).
- `StockTransaction.product` → `Product` (PROTECT); `.user` → `User` (SET_NULL);
  optional `.source_purchase` → `PurchaseOrder`.
- `PurchaseOrder.supplier` → `Supplier` (PROTECT); `PurchaseItem` is a child of `PurchaseOrder` (CASCADE).
- `Profile` is one-to-one with `User`, auto-created via signal.

**Indexes & constraints** (selected)
- Indexed: `Product.sku`, `Product.barcode`, `Product.status`, `(category, status)`,
  `StockTransaction (product, -created_at)` and `(transaction_type, -created_at)`,
  `PurchaseOrder (status, -order_date)`.
- Unique: `Product.sku`, `Category.name/slug`, `PurchaseOrder.po_number`,
  `unique_product_per_po` (a product appears once per PO), conditional unique supplier (name + GST).
- Check: product prices `>= 0`.

---

## Roles & Permissions

Core / inventory roles:

| Capability                          | Admin | Manager | Staff | Auditor |
|-------------------------------------|:-----:|:-------:|:-----:|:-------:|
| View dashboard / lists / reports    | ✅    | ✅      | ✅    | ✅      |
| Export reports (Excel/CSV/PDF)      | ✅    | ✅      | ✅    | ✅      |
| Create stock transactions           | ✅    | ✅      | ✅    | ❌      |
| Manage products / categories        | ✅    | ✅      | ❌    | ❌      |
| Manage suppliers / purchases        | ✅    | ✅      | ❌    | ❌      |
| Manage users & roles                | ✅    | ❌      | ❌    | ❌      |
| Django admin                        | ✅*   | ❌      | ❌    | ❌      |
| API write (POST/PUT/PATCH/DELETE)   | ✅    | ✅†     | staff‡| ❌      |

Production / work-order roles (Admin & Manager can do all of these too):

| Capability                          | Planner | Supervisor | Technician |
|-------------------------------------|:-------:|:----------:|:----------:|
| Create work orders & manage BOMs    | ✅      | ❌         | ❌         |
| Release & reserve materials         | ✅      | ❌         | ❌         |
| Assign work orders                  | ❌      | ✅         | ❌         |
| Start / complete assigned orders    | ❌      | ✅         | ✅         |

\* Superusers always pass every check.
† Managers can write to all resources. ‡ Staff may only `POST` stock transactions.
The **Auditor** is a read-only oversight role — full visibility (incl. the Activity
Log), no writes anywhere (UI or API). Enforcement: `accounts/permissions.py`
(`AdminRequiredMixin`, `ManagerRequiredMixin`, `StockRecorderRequiredMixin`,
`RoleRequiredMixin`) for views and `api/permissions.py`
(`IsManagerOrReadOnly`, `IsStaffCanCreate`) for the API.

---

## Quick Start (Local)

### Prerequisites
- Python 3.12+ (3.14 supported — see compatibility note at the top)
- PostgreSQL running locally *(optional — the project ships configured for SQLite)*

```bash
# 1. Clone & enter
cd inventory_management

# 2. Virtual env
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env                 # then set SECRET_KEY (and DB_* if using Postgres)

# 5. Migrate & seed
python manage.py migrate
python manage.py seed_data           # demo users + sample catalog
python manage.py createsuperuser     # optional, your own admin

# 6. Run
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and log in:

| User         | Password      | Role             |
|--------------|---------------|------------------|
| `admin`      | `password123` | Admin            |
| `manager`    | `password123` | Inventory Manager|
| `staff`      | `password123` | Staff            |
| `auditor`    | `password123` | Auditor (read-only)|
| `planner`    | `password123` | Production Planner |
| `supervisor` | `password123` | Floor Supervisor |
| `technician` | `password123` | Technician       |

`seed_data` also creates a sample Bill of Materials and a draft work order
(`SWO-2026-001`) so you can try the production flow immediately. For extra
time-spread history (useful for the report date filters), run
`python manage.py seed_history`.

#### Database choice

- **SQLite (default).** The shipped `.env` sets `DB_ENGINE=sqlite`, so the steps above
  work with zero database setup.
- **PostgreSQL.** In `.env`, set `DB_ENGINE=postgresql` and the `DB_NAME` / `DB_USER` /
  `DB_PASSWORD` / `DB_HOST` / `DB_PORT` values, create the database, then re-run
  `migrate` and `seed_data`:
  ```sql
  -- sudo -u postgres psql
  CREATE DATABASE inventory_db;
  CREATE USER inventory_user WITH PASSWORD 'inventory_pass';
  GRANT ALL PRIVILEGES ON DATABASE inventory_db TO inventory_user;
  ALTER DATABASE inventory_db OWNER TO inventory_user;
  ```

> **⚠️ Always run with the virtual environment active.** If you launch with a
> *global* Python that has an older Django, you'll hit a Python-3.14 template crash
> (`'super' object has no attribute 'dicts'`). The `runserver` startup banner should
> read **`Django version 6.0.x`**. In VS Code, pick the `.venv` interpreter
> (Ctrl+Shift+P → *Python: Select Interpreter*) so the Run button uses it.

---

## Running with Docker

The compose stack runs **PostgreSQL + Gunicorn (web) + Nginx**, runs migrations,
collects static, and seeds demo data automatically.

```bash
cp .env.example .env        # set a real SECRET_KEY; DEBUG=False for prod-like
docker compose up --build
```

- App via Nginx: <http://localhost/>
- App direct (Gunicorn): <http://localhost:8000/>

To disable auto-seeding, set `SEED_DATA: "false"` on the `web` service.

---

## Frontend (Tailwind CSS)

The UI is built with **Tailwind CSS** plus **Alpine.js** for small interactions
(sidebar toggle, dropdowns, dismissible alerts). Both are loaded from a CDN — there
is **no Node build step**, so the project runs with Python alone.

- **Shared styles** live in [`templates/partials/tailwind_head.html`](templates/partials/tailwind_head.html):
  the Tailwind Play CDN, the theme config (`brand` color palette) and reusable
  component classes (`.btn`, `.card`, `.badge`, `.form-input`…) defined with `@apply`.
- **Forms** are plain Django forms. Widget classes are applied by `StyledFormMixin`
  ([`accounts/forms.py`](accounts/forms.py)) and rendered by
  [`templates/partials/field.html`](templates/partials/field.html) /
  [`form_fields.html`](templates/partials/form_fields.html).

### Switching to a Tailwind build (production)

The Play CDN prints a "not for production" console warning and recompiles styles in
the browser. For production you can swap it for a precompiled stylesheet:

```bash
npm install -D tailwindcss
npx tailwindcss init
# Configure `content: ["./templates/**/*.html"]`, move the @layer components
# block from tailwind_head.html into an input.css, then build:
npx tailwindcss -i input.css -o static/css/tailwind.css --minify
```

Then replace the CDN `<script>`/`<style>` in `tailwind_head.html` with
`<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">`. Nothing else
changes — all templates already use standard Tailwind utility classes.

---

## REST API

Base URL: `/api/`  ·  Browsable API & login at `/api/auth/`.

| Endpoint                      | Methods                | Notes |
|-------------------------------|------------------------|-------|
| `/api/products/`              | GET, POST, PUT, DELETE | filter `category,status,unit`; search `name,sku,barcode` |
| `/api/products/low_stock/`    | GET                    | products at/below reorder level |
| `/api/categories/`            | CRUD                   | |
| `/api/suppliers/`             | CRUD                   | filter `is_active` |
| `/api/transactions/`          | GET, POST              | staff may create; managers may edit/delete |
| `/api/purchases/`             | CRUD                   | nested line items |
| `/api/purchases/{id}/receive/`| POST                   | receive stock for the order |
| `/api/dashboard/`             | GET                    | aggregate KPIs |
| `/api/auth/token/`            | POST                   | obtain auth token |

**Auth example**

```bash
# Get a token
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
     -d "username=admin&password=password123"

# Use it
curl http://127.0.0.1:8000/api/products/?stock=low \
     -H "Authorization: Token <your-token>"
```

All list endpoints are paginated (`?page=`, 25/page) and support `?ordering=` and `?search=`.

---

## Reports & Exports

Available at `/reports/`:

| Report          | Filters                                  | Formats          |
|-----------------|------------------------------------------|------------------|
| Inventory       | date range (activity), category          | Excel / CSV / PDF|
| Stock Movement  | quick range (7/15/30/90d, month), type   | Excel / CSV / PDF|
| Low Stock       | —                                        | Excel / CSV / PDF|
| Purchase        | quick range, status                      | Excel / CSV / PDF|

- **Quick date ranges** (Last 7/15/30/90 days, This month, All time) plus a custom
  From/To picker; the active window is shown as a badge (e.g. *"18 rows · 26 May → 01 Jun"*).
- **Movement type** filter on Stock Movement (Stock In / Out / Adjustment).
- Every report has a serial **No.** column, and **exports use the active filters**.

Purchase orders also have a printable **Purchase Order / Invoice PDF**
(`/purchases/<id>/invoice/`), with company header, supplier block, itemized table and
totals — configurable via `COMPANY_*` / `CURRENCY_SYMBOL` settings.

---

## Production / Work Orders (SWO)

A light manufacturing layer at `/production/`:

1. Define a **Bill of Materials** on a product (Product detail → *Add Bill of Materials*).
2. **Planner** creates a work order; components are auto-filled from the BOM × quantity.
3. **Release & Reserve** soft-allocates component stock (`available = on-hand − reserved`);
   release is blocked if a component is short.
4. **Supervisor** assigns the order to a **Technician**.
5. **Technician** starts and completes it — components are consumed (Stock Out) and, for
   *assembly* orders, the finished product is produced (Stock In). All movements flow
   through `StockTransaction`, so history, the dashboard and the audit log stay consistent.

Low-stock alerts are **reserved-aware** — material promised to a work order no longer
counts as available.

---

## Testing

```bash
python manage.py test                      # full suite (50+ tests)
python manage.py test inventory.tests_qa -v 2   # the end-to-end QA checklist
```

`inventory/tests_qa.py` is an end-to-end QA suite mapped to the manual checklist: auth
flows, stock transactions, purchases (add-row + partial receiving + invoice PDF), the
work-order lifecycle, report filters, the full role-permission matrix, and the API.

Covers the core invariants: stock in/out/adjustment math, audit snapshots,
low-stock detection, purchase total calculation, and idempotent stock receiving.

---

## Production Deployment (Ubuntu + Nginx + Gunicorn)

```bash
# 1. System packages
sudo apt update && sudo apt install -y python3-venv python3-pip postgresql nginx

# 2. Code + venv
sudo mkdir -p /var/www/inventory_management
sudo chown $USER:$USER /var/www/inventory_management
cd /var/www/inventory_management
git clone <your-repo> .            # or copy the project here
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
#   set DEBUG=False, a strong SECRET_KEY, ALLOWED_HOSTS=your-domain.com,
#   and the production DB_* credentials.

# 4. Database (see Quick Start step 5), then:
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# 5. Gunicorn via systemd
sudo cp deploy/gunicorn.service /etc/systemd/system/inventory.service
sudo systemctl daemon-reload
sudo systemctl enable --now inventory

# 6. Nginx
sudo cp deploy/nginx-bare-metal.conf /etc/nginx/sites-available/inventory
sudo ln -s /etc/nginx/sites-available/inventory /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# 7. HTTPS (recommended)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

With `DEBUG=False`, settings automatically enable HSTS, secure cookies,
SSL redirect and other hardening (see `config/settings.py`).

### Migration strategy
- Migrations are committed per app under `<app>/migrations/`.
- Deploy flow: pull code → `pip install -r requirements.txt` → `python manage.py migrate`
  → `collectstatic` → restart Gunicorn (`sudo systemctl restart inventory`).
- For zero-downtime, run `migrate` before restarting workers; keep migrations
  backwards-compatible (add columns nullable first, backfill, then enforce).

---

## Configuration Reference

All configuration is environment-driven (`.env`). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | dev key | **Set a strong value in production.** |
| `DEBUG` | `True` | Toggle debug + auto-hardening when False |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hosts |
| `DB_ENGINE` | `postgresql` | Set `sqlite` for a zero-setup trial |
| `DB_NAME/USER/PASSWORD/HOST/PORT` | — | PostgreSQL connection |
| `EMAIL_*` | — | SMTP for password reset (console backend when DEBUG) |
| `LOW_STOCK_GLOBAL_THRESHOLD` | `10` | Fallback low-stock threshold |
| `COMPANY_NAME / COMPANY_ADDRESS / COMPANY_EMAIL / COMPANY_PHONE / COMPANY_TAX_ID` | sample values | Header on the Purchase Order / Invoice PDF |
| `CURRENCY_SYMBOL` | `` (none) | Prefix for money amounts on the invoice PDF |
| `SEED_DATA` (Docker) | `true` | Auto-seed sample data on container start |

---

## License

Provided as a reference implementation — adapt freely for your business.
