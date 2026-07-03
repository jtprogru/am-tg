FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependency layer: cached until pyproject.toml/uv.lock change
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.14-slim AS runtime

RUN groupadd --gid 10001 amtg \
    && useradd --uid 10001 --gid amtg --no-create-home --shell /usr/sbin/nologin amtg

WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src
ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001
EXPOSE 9119

CMD ["uvicorn", "am_tg.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "9119"]
