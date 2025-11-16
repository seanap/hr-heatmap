FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# System deps for Pillow/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy source into /srv/app (package name = app)
COPY app /srv/app

# Python deps
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    numpy \
    pandas \
    pillow \
    matplotlib \
    pytz \
    garminconnect \
    && rm -rf /root/.cache

EXPOSE 8000

# NOTE: use app.main:app here so relative imports (from .config ...) work
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
