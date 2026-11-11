FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/model-cache \
    HF_HUB_DISABLE_XET=1 \
    OMP_NUM_THREADS=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agileops \
    && mkdir -p /data && touch /data/.initialized && chown -R agileops:agileops /data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade 'pip>=26.2' \
    && python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && python -m pip install --no-cache-dir '.[ai]'

USER agileops
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "agileops.main:app", "--host", "0.0.0.0", "--port", "8000"]
