# FleetOps API

[![CI](https://github.com/maksym-potapchuk/fleetops-api/actions/workflows/ci.yml/badge.svg)](https://github.com/maksym-potapchuk/fleetops-api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/django-5.2-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.16-A30000)
![PostgreSQL](https://img.shields.io/badge/postgresql-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-7-DC382D?logo=redis&logoColor=white)

Backend for a vehicle fleet operations platform — a pet project where I designed and built the server side end to end: data model, REST API, auth, caching, real-time notifications, tests and CI.

The API covers the whole lifecycle of a vehicle in a rental/leasing fleet: intake and preparation, driver assignment, scheduled maintenance, expenses and invoices, and alerts when something is due.

---

## Highlights

- **REST API** on Django REST Framework, versioned under `/api/v1/`, 7 domain apps, ~40 models
- **HttpOnly-cookie JWT auth** with token rotation, blacklisting and per-scope throttling
- **Signal-driven domain events** — driver history and flags stay consistent no matter where a change comes from (API, admin, shell)
- **Two-tier Redis caching** with versioned list keys and transaction-safe invalidation
- **Real-time notifications** over Server-Sent Events (Django Channels, ASGI)
- **Polymorphic expense model** with category-specific details and auto-computed totals
- **600+ tests**, Ruff lint/format and Docker build in GitHub Actions

## Tech Stack

| Area | Technology |
|------|------------|
| Language | Python 3.12 |
| Framework | Django 5.2, Django REST Framework 3.16 |
| Auth | SimpleJWT 5.5 (HttpOnly cookies) |
| Database | PostgreSQL 16 (psycopg 3) |
| Cache / pub-sub | Redis 7, channels-redis |
| Async | Django Channels 4, Uvicorn (ASGI) |
| Storage | Local filesystem or S3 (django-storages) |
| Metrics | django-prometheus |
| Tooling | Poetry, Ruff, Docker, GitHub Actions, Dependabot |

## Architecture

```
            ┌──────────────────────────┐
 clients ──▶│   Django + DRF (ASGI)    │──▶ /metrics (Prometheus)
 (web/bot)  │  REST /api/v1  ·  SSE    │
            └────────────┬─────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │PostgreSQL │   │   Redis   │   │ Local/S3  │
   │   data    │   │cache+pubsub│  │   media   │
   └───────────┘   └───────────┘   └───────────┘
```

```
backend/
├── config/            # settings, URL root, ASGI, cache utils, layout-aware search, storage helpers
├── account/           # custom User (UUID, email login), cookie JWT auth, preferences
├── driver/            # drivers, phone validation, signal-managed flags
├── vehicle/           # vehicles, Kanban statuses, photos, inspections, mileage, owners, documents
├── fleet_management/  # maintenance regulations, service plans, equipment, service providers
├── expense/           # polymorphic expenses, invoices, categories
└── notification/      # notification rules, delivery, preferences, SSE stream
```

---

## Domain & Business Logic

### Authentication

Tokens never reach JavaScript — clients send cookies with `withCredentials`.

- `access_token` (5 min) + `refresh_token` as HttpOnly, SameSite=Lax cookies
- **Remember me** switches between a persistent and a session cookie
- **Rotation + blacklisting** — every refresh issues a new pair and blacklists the old one
- **Recovery endpoint** (`auth/unset-session/`) clears broken cookies to break redirect loops
- **Throttling**: separate rates for auth, authenticated and anonymous traffic

### Vehicles

- **11 statuses** forming a Kanban pipeline: `AUCTION → FOCUS → GAS_INSTALL → SERVICE → CLEANING → PRE_DELIVERY → READY → RENT → LEASING → SELLING → SOLD`
- **Sparse positioning** — 1000-unit gaps in `status_position` allow inserts without renumbering; a batch reorder endpoint handles cross-column moves
- **Status history** records every transition with its source (manual, reorder, creation)
- **Safe deletion**: `DELETE` archives (reversible) → `delete-check/` reports related data → `permanent-delete/?confirm=true` hard-deletes
- Sub-resources: photos, technical inspections, mileage logs, ownership history, registration documents

### Driver Assignment via Signals

Assignment is tracked in `pre_save` / `post_save` / `pre_delete` signals, not in views, so every entry point behaves the same:

- assigning opens a `VehicleDriverHistory` record, unassigning closes it
- `Driver.has_vehicle` is toggled automatically
- cache invalidation runs in `transaction.on_commit()` — nothing is cleared for rolled-back writes

### Maintenance Regulations

- **Schema → Items** (e.g. "oil change every 10,000 km, notify 1,000 km before")
- Assigning a schema creates per-vehicle entries tracking `last_done_km`; `next_due_km`, `is_due()` and `km_remaining()` are computed
- Immutable event history (performed / km updated / notified)
- Exactly one default schema, enforced by a partial `UniqueConstraint` plus `select_for_update()`
- Service plans and a default equipment checklist granted to every new vehicle

### Expenses

A single `Expense` model with category-specific detail models resolved through a `DETAIL_MAP`:

| Category | Details | Amount |
|----------|---------|--------|
| Fuel | liters, fuel type | manual |
| Service | service provider + line items | sum of items |
| Parts / Accessories / Documents | name, qty, unit price | Σ qty × price |
| Washing | exterior / interior / full | manual |
| Inspection | official + additional cost | sum of costs |
| Fines | fine number, violation, driver at the time | manual |

- Inspection expenses create a linked technical inspection automatically
- Invoices are grouped and searchable; uploads are type-validated
- Multipart requests carry nested line items as JSON fields

### Notifications

- Rules for due maintenance, inspections and other events, with per-user preferences
- Pushed to clients over **SSE** (`/api/v1/notifications/stream/`) via Channels and a Redis channel layer; pushes fire only after the transaction commits
- Unread counters and read / read-all endpoints

---

## Engineering Decisions

### Two-tier Redis cache

```
list caches   vehicle:list:v{N}:{query_hash}   versioned — any write bumps N
detail caches vehicle:detail:{pk}              deleted on update / delete
```

- **Fault-tolerant** — every cache call is wrapped, so a Redis outage is just a cache miss
- **Transaction-safe** — invalidation is deferred to `on_commit()`
- TTLs are configurable per entity via environment variables

### Keyboard-layout-aware search

`LayoutAwareSearchFilter` converts the query between EN and UA keyboard layouts and ORs the variants — typing `Njqjnf` still finds `Тойота`.

### Storage abstraction

`media_url()` returns relative paths for local storage and absolute URLs for S3, so serializers don't change between environments.

### Auto-translation

Regulation titles are stored in several languages; missing translations are filled through `deep-translator`.

---

## API Overview

Base path: `/api/v1/`

| Resource | Prefix | What it does |
|----------|--------|--------------|
| Auth | `auth/` | login, refresh, logout, profile, preferences, session recovery |
| Drivers | `driver/` | CRUD with filtering and layout-aware search |
| Vehicles | `vehicle/` | CRUD, Kanban reorder, archive/restore, photos, inspections, mileage, owners |
| Fleet | `fleet/` | service providers, regulation schemas and plans, service plans, equipment |
| Expenses | `expense/` | expenses by category, invoices, categories |
| Notifications | `notifications/` | list, unread count, read / read-all, SSE stream |

All list endpoints are paginated and support `django-filter` query params.

---

## Getting Started

**Requirements:** Python 3.12, Poetry 2, PostgreSQL 16, Redis 7.

```bash
# start dependencies (or use local installs)
docker run -d --name fleetops-db -p 5432:5432 \
  -e POSTGRES_DB=fleetops -e POSTGRES_USER=fleetops -e POSTGRES_PASSWORD=fleetops postgres:16-alpine
docker run -d --name fleetops-redis -p 6379:6379 redis:7-alpine

cd backend
cp .env.example .env          # set POSTGRES_* to the values above, POSTGRES_HOST=localhost
poetry install --no-root
poetry run python manage.py migrate
poetry run python manage.py seed_expense_categories
poetry run python manage.py create_vehicle_reg_basic_schema
poetry run python manage.py createsuperuser
poetry run uvicorn config.asgi:application --reload
```

Or build the image: `docker build -t fleetops-api backend/`.

## Testing

```bash
cd backend
poetry run python manage.py test --settings=config.test_settings
```

- Django `TestCase` with per-test DB isolation; tests run on in-memory SQLite and `LocMemCache`, no external services needed
- JWT injected through `client.cookies["access_token"]`
- Coverage: auth flows, CRUD, signal side effects, validation, read-only field protection, `PROTECT` constraints, archive/restore, expense calculations, regulation logic, notifications

## CI

```
push / PR ──▶ backend-lint (ruff check + format) ──┐
          └─▶ backend-test (PostgreSQL + Redis)  ──┴──▶ docker build
```

Dependabot keeps pip packages and GitHub Actions up to date.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django core |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | database |
| `REDIS_URL` | cache and channel layer |
| `ACCESS_TOKEN_LIFETIME`, `REFRESH_TOKEN_LIFETIME` | JWT lifetimes (seconds) |
| `SECURE_COOKIES` | `Secure` flag on auth cookies (HTTPS only) |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | allowed client origins |
| `THROTTLE_ANON`, `THROTTLE_USER`, `THROTTLE_AUTH` | rate limits |
| `USE_S3`, `AWS_*` | optional S3 media storage |
| `CACHE_TTL_*` | per-entity cache TTLs |

---

Built by [Maksym Potapchuk](https://github.com/maksym-potapchuk).
