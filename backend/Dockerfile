FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    packages="libdeflate0 libicu76 tesseract-ocr tesseract-ocr-chi-sim libgomp1"; \
    for attempt in 1 2 3; do \
        apt-get update -o Acquire::Retries=5 \
        && apt-get install -y --no-install-recommends --fix-missing -o Acquire::Retries=5 $packages \
        && break; \
        apt-get install -y -f -o Acquire::Retries=5 || true; \
        dpkg --configure -a || true; \
        if [ "$attempt" = "3" ]; then exit 1; fi; \
        rm -rf /var/lib/apt/lists/*; \
        sleep 5; \
    done; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=3).read()"

CMD ["sh", "-c", "alembic upgrade head && if [ \"${BOOTSTRAP_DEMO_DATA:-false}\" = \"true\" ]; then python -m app.scripts.bootstrap_demo; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
