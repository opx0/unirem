# Campus Radar

A private, mobile-first Django notice and action manager. The manual core does not require AI, an email provider or university access.

## Run locally

Install Python 3.13+, [uv](https://docs.astral.sh/uv/) and optionally Docker. `docker compose up --build` starts PostgreSQL and the development web server at http://127.0.0.1:8000. For a lightweight SQLite run, omit `POSTGRES_HOST` and use:

```sh
uv sync --frozen
DJANGO_DEBUG=1 uv run python manage.py migrate
DJANGO_DEBUG=1 uv run python manage.py runserver
```

Register at `/register/`, complete Settings, then Capture a notice and add events and tasks on its detail page. For admin demonstration, create a superuser with `DJANGO_DEBUG=1 uv run python manage.py createsuperuser`; admin is at `/admin/`. Never use development settings for a public deployment.

Optional synthetic records for an existing account: `DJANGO_DEBUG=1 uv run python manage.py seed_demo YOUR_USERNAME`. The command is idempotent and never schedules reminders.

## Quality gate

```sh
uv run ruff check .
uv run ruff format --check .
DJANGO_DEBUG=1 uv run python manage.py check
DJANGO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run
```

See the [feature map](docs/product.md), [domain model](docs/domain.md), and [roadmap and course demonstration](docs/roadmap.md). This is a local academic release, **not** a production-ready deployment or a complete PWA. No email, AI extraction or reminder delivery is claimed.
