# Multi-stage build for the Baiterek API (FastAPI, Python 3.12).
# Stage 1 builds wheels for the project and all dependencies; the runtime
# stage installs from those wheels only, so no build toolchain ships in the
# final image. docker-compose targets the `runtime` stage.

FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY app ./app

RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Source tree is kept in the image (alongside the installed package) so that
# `alembic upgrade head` and `python -m app.seed` work from /app.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
