# syntax=docker/dockerfile:1
# Bloomy News dashboard — python:3.11-slim, non-root, healthcheck.
# Build with:  docker build -t bloomy-news .
# Run with:    docker run --rm -p 127.0.0.1:8080:8080 bloomy-news
#
# NOTE: the dashboard server binds 127.0.0.1:8080 inside the container.
# The -p flag maps container 8080 to host 127.0.0.1:8080 only — the
# service is not exposed to the LAN. To run the pipeline or scheduler,
# override CMD:
#   docker run --rm -v "$(pwd)/news.db:/app/news.db" bloomy-news \
#     python news_tool.py
#   docker run --rm bloomy-news python scripts/scheduler.py --verify

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user (uid 1000 to match the typical desktop user).
RUN groupadd --gid 1000 bloomy \
    && useradd --uid 1000 --gid bloomy --shell /bin/bash --create-home bloomy

WORKDIR /app

# Install deps first so this layer is cached independently of source.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the rest of the source.
COPY . .

# Fix ownership for non-root execution.
RUN chown -R bloomy:bloomy /app
USER bloomy

# Dashboard listens on 8080 inside the container.
EXPOSE 8080

# Healthcheck hits the dashboard root. Uses urllib (stdlib) to avoid
# adding a new dependency for the probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/', timeout=3).read()" || exit 1

# Default command runs the dashboard server.
CMD ["python", "dashboard/serve.py"]
