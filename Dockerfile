FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY run_eval.py ./run_eval.py
COPY pyproject.toml ./pyproject.toml

RUN mkdir -p /data

# Runtime state lives on the named volume (see docker-compose.yml).
ENV DATABASE_URL=sqlite:////data/rafterflow.db \
    NOTIFICATIONS_LOG_PATH=/data/notifications.log \
    AUDIT_LOG_PATH=/data/enquiry_audit.jsonl

EXPOSE 8000

ENTRYPOINT ["python", "scripts/docker_entrypoint.py"]
