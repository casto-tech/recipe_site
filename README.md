# The Recipe Book

A single-page recipe website built with Django, HTMX, Alpine.js, and Tailwind CSS. Browse and search a personal recipe collection with real-time filtering and a smooth card-flip detail view. Deployed on Azure Container Apps with PostgreSQL and Azure Blob Storage.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.12
- Git

---

## Local Setup

Three steps from clone to running site:

```bash
# 1. Clone and configure environment
git clone <repo-url> recipe_site
cd recipe_site
cp .env.example .env
# Edit .env — generate a real DJANGO_SECRET_KEY and DB_PASSWORD:
# python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2. Start the application
docker-compose up --build -d

# 3. Load sample data
docker-compose exec web python manage.py load_sample_recipes
```

Visit [http://localhost:8000](http://localhost:8000) to see the site.

---

## Running Tests

```bash
docker-compose exec web pytest tests/ -v
```

Or locally (outside Docker) with a running PostgreSQL instance:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

The test suite requires ≥80% code coverage to pass.

---

## Managing Recipes (Local Admin)

> **The admin interface is only available when running locally.** It does not exist on the production site — the URL is never mounted and the admin package is not installed in the production Docker image.

**Create a superuser:**

```bash
docker-compose exec web python manage.py createsuperuser
```

**Access the admin:**

Open [http://localhost:8000/management/](http://localhost:8000/management/) and log in with your superuser credentials.

From the admin you can:

- **Create and edit Recipes** — title, slug (auto-generated), image upload (with live preview), ingredients (one per line), directions (one step per line), and tag assignment via the side-by-side picker.
- **Create and edit Tags** — name and auto-generated slug.

**Ingredient format:** enter one ingredient per line, e.g.:
```
2 cups flour
1 tsp baking powder
3 eggs
```

**Directions format:** enter one step per line — they are displayed as a numbered list:
```
Preheat oven to 180°C.
Mix dry ingredients in a bowl.
Add wet ingredients and stir until combined.
```

---

## Deployment

Deployment is automated via GitHub Actions on every push to `main`:

1. `ci.yml` — runs tests, coverage, linting (flake8, black)
2. `security.yml` — runs pip-audit, bandit SAST, and Trivy Docker image CVE scan
3. `deploy.yml` — builds the Docker image (with `ADMIN_ENABLED=False`), pushes to Azure Container Registry, deploys a new revision to Azure Container Apps, runs migrations, and verifies the health endpoint

**The admin is completely disabled in production.** The production Docker image is built with `ADMIN_ENABLED=False` and `django.contrib.admin` is removed from `INSTALLED_APPS`. Any request to `/management/` or `/admin/` returns HTTP 404.

For deployment prerequisites and Azure setup, see [infrastructure_outline.md](infrastructure_outline.md).

---

## Environment Variables

Copy `.env.example` to `.env` for local development. See `.env.example` for all variables with descriptions.

| Variable | Local Dev | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Generate with `secrets.token_urlsafe(64)` | Django signing key — min 50 chars |
| `DJANGO_DEBUG` | `True` | Debug mode — always `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hostnames |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | Settings module to load |
| `ADMIN_ENABLED` | `True` | Mounts admin at `/management/` — local dev only |
| `DB_NAME` | `recipes` | PostgreSQL database name |
| `DB_USER` | `recipes_user` | PostgreSQL username |
| `DB_PASSWORD` | Generate with `secrets.token_urlsafe(32)` | PostgreSQL password |
| `DB_HOST` | `db` (Docker service name) | Database host |
| `DB_PORT` | `5432` | Database port |
| `AZURE_STORAGE_ACCOUNT_NAME` | *(empty)* | Azure Storage account — blank = local filesystem |
| `AZURE_STORAGE_ACCOUNT_KEY` | *(empty)* | Azure Storage key — blank in local dev |
| `AZURE_STORAGE_CONTAINER` | `media` | Blob container name |
