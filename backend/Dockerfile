FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Every dependency ships a manylinux wheel, so no compiler or libpq headers are needed.
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 app
COPY --chown=app:app . .
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)"

CMD ["sh", "start.sh"]
