# Community Edition backend image.
# Build context: ./backend
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# All Python deps ship prebuilt wheels (psycopg[binary] bundles libpq), so no
# compiler toolchain is needed.
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Chromium (+ its system libraries) for server-side PDF export.
RUN playwright install --with-deps chromium

COPY . ./

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
