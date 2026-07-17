FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Dependency layer first for build caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/
RUN uv sync --frozen --no-dev

# Non-root: this container handles children's audio streams
RUN useradd -m worker && chown -R worker /app
USER worker

# Pre-download any model/plugin assets at build time, not per cold start
RUN uv run python -m commander_sky.main download-files || true

CMD ["uv", "run", "python", "-m", "commander_sky.main", "start"]
