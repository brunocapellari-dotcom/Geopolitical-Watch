FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# The upstream slim image can lag Debian point-security packages between image
# rebuilds. Apply available security fixes before installing the application,
# then remove APT metadata so the final runtime remains small.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY geowatch /app/geowatch
RUN pip install --no-cache-dir ".[production]"

COPY config /app/config
COPY sql /app/sql
COPY scripts /app/scripts
COPY knowledge /app/knowledge

# Cloud Run, Railway and other container runtimes require the HTTP server to
# listen on all container interfaces. PORT remains runtime-overridable.
# The application still enforces its own private session/Bearer authentication.
USER 65532:65532

EXPOSE 8080
CMD ["python", "-m", "geowatch", "serve"]
