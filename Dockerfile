# syntax=docker/dockerfile:1

# Multi-stage to keep runtime slim while ensuring build tools available at start
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system deps needed at runtime and build time (gcc, cython, headers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       python3-dev \
       git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project
COPY . /app

# Install Python deps; include libs similar to the provided conda environment
RUN pip install --upgrade pip setuptools wheel \
    && pip install \
       cython \
       numpy \
       scipy \
       ujson \
       uvloop \
       objgraph \
       packaging \
       python-graph-core \
       pygraph \
       pykalman \
       scikit-base \
       gcc

# Ensure entrypoint is executable; ensure server script is executable if present
RUN chmod +x /app/docker-entrypoint.sh || true \
    && chmod +x /app/mlat-server/mlat-server || true

# Create a non-root user for runtime
RUN useradd -u 10001 -m appuser \
    && chown -R appuser:appuser /app

USER appuser

# Expose default JSON client port
EXPOSE 40147/tcp

# Declare workdir as a volume so it can be bound from host
VOLUME ["/app/workdir"]

# Entrypoint script compiles on each start and launches server
ENTRYPOINT ["/app/docker-entrypoint.sh"]
