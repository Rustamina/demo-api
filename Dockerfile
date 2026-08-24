FROM python:3.12-slim AS builder
WORKDIR /build

COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN useradd -u 1000 -m -s /bin/bash appuser

COPY --from=builder /install /usr/local
COPY --chown=1000:1000 app/main.py .
RUN chmod 644 /app/main.py

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
