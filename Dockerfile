# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: install dependencies with uv into a project-local virtualenv
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
COPY README.md ./
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2: slim runtime — just the venv + source, non-root user
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH"

RUN groupadd -r mcp && useradd -r -g mcp mcp
WORKDIR /app

COPY --from=builder --chown=mcp:mcp /app/.venv ./.venv
COPY --from=builder --chown=mcp:mcp /app/src ./src

USER mcp
EXPOSE 8000

# Only used when TRANSPORT=http (see src/fbi_crime_data_mcp/server.py);
# irrelevant/no-op for the default stdio transport.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=3)"]

ENTRYPOINT ["fbi-crime-data-mcp"]
