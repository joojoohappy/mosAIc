# Local integration image (used by the root docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app
# print() buffers when stdout isn't a TTY (i.e. under docker compose),
# which would silently swallow the tryReady startup warning below.
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY data data
COPY scripts scripts

# .env is NOT copied (see .dockerignore) -- the key comes in via compose env_file
# at runtime so it never gets baked into the image layer.
# --no-proxy-headers: never let X-Forwarded-For rewrite the client address used
# by the per-visitor limits (see app/limits.py client_id).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
