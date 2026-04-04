# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Install system build dependencies and Python packages.
# Compilers and dev headers never reach the final image.
FROM python:3.12-slim AS builder

# Install system dependencies needed to compile Python packages (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a custom prefix so we can copy them cleanly
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt


# ── Stage 2: Final Image ──────────────────────────────────────────────────────
# Minimal runtime image — no build tools, no compilers.
FROM python:3.12-slim

# Install only the runtime system library (no dev headers, no compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create a non-root system user and group
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set working directory
WORKDIR /app

# Copy source code (see .dockerignore for exclusions)
COPY --chown=appuser:appgroup . /app/

# Collect static files during build (uses a dummy SECRET_KEY for collectstatic only)
# The real SECRET_KEY is never baked into the image — it is injected at runtime.
ARG DJANGO_SECRET_KEY=build-time-placeholder-not-used-at-runtime
ARG DJANGO_SETTINGS_MODULE=config.settings.production
ARG ADMIN_ENABLED=False
ENV DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY} \
    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    ADMIN_ENABLED=${ADMIN_ENABLED} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python manage.py collectstatic --noinput

# Switch to non-root user before running the application
USER appuser

# Only expose the application port — never the database port
EXPOSE 8000

# Run Gunicorn with 2 workers (sufficient for a recipe site; scale via replicas)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
