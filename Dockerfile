FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir ".[production]"
EXPOSE 8080
CMD ["python", "-m", "geowatch", "serve"]
