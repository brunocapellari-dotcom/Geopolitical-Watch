FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY geowatch /app/geowatch
RUN pip install --no-cache-dir ".[production]"

COPY config /app/config
COPY sql /app/sql
COPY scripts /app/scripts
COPY knowledge /app/knowledge

# Cloud Run does not require a privileged process. Numeric UID/GID avoids
# introducing another account-management package into the image.
USER 65532:65532

EXPOSE 8080
CMD ["python", "-m", "geowatch", "serve"]
