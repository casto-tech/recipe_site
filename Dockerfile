# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Install system build dependencies and Python packages.
# Compilers and dev headers never reach the final image.
FROM python:3.12-slim AS builder

# Install system dependencies needed to compile Python packages (psycopg2).
# apt-get upgrade applies available OS security patches so fixable CVEs don't
# block Trivy scans.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download Tailwind CSS standalone CLI — compiled to a static bundle in the final stage.
# Binary is copied across, runs once, then deleted; it never ships at runtime.
ARG TAILWIND_VERSION=3.4.17
RUN curl -fsSL \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-linux-x64" \
    -o /tailwindcss \
    && chmod +x /tailwindcss

# Install Python dependencies into a custom prefix so we can copy them cleanly.
# INSTALL_DEV=true adds pytest, coverage, linting tools (used in docker-compose dev builds).
ARG INSTALL_DEV=false
COPY requirements.txt requirements-dev.txt /tmp/
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir --prefix=/install -r /tmp/requirements-dev.txt; \
    else \
        pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt; \
    fi


# ── Stage 2: Final Image ──────────────────────────────────────────────────────
# Minimal runtime image — no build tools, no compilers.
FROM python:3.12-slim

# Install only the runtime system library (no dev headers, no compiler).
# apt-get upgrade patches any OS CVEs that have fixes available.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
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

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Compile Tailwind CSS to a static bundle — eliminates the CDN script in production.
# Binary comes from the builder stage; deleted immediately after so it never ships.
COPY --from=builder /tailwindcss /usr/local/bin/tailwindcss
RUN tailwindcss \
    -c tailwind.config.js \
    -i static/css/tailwind.input.css \
    -o static/css/tailwind.output.css \
    --minify \
    && rm /usr/local/bin/tailwindcss

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

# Run migrations then start Gunicorn
CMD ["/app/entrypoint.sh"]
