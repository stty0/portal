# Portal Backend (FastAPI) — backend-design §5.2
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 의존성만 먼저 설치해 소스 변경 시 레이어 캐시가 살아남게 한다.
COPY pyproject.toml ./
COPY app/__init__.py ./app/
RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir "uvicorn[standard]>=0.30"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# 루트로 돌리지 않는다.
RUN useradd --uid 10001 --create-home portal
USER 10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
