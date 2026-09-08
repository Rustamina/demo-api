"""
demo-api — учебный сервис для DevOps-практики.

Все ручки специально сделаны так, чтобы на них можно было отработать
типовые сценарии Kubernetes: пробы, rolling update, HPA, алерты, OOMKilled.
"""
import os
import time
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ---------------------------------------------------------------- конфигурация
# Значения приезжают из ConfigMap (GREETING, LOG_LEVEL) и Downward API (POD_*).
VERSION = os.getenv("APP_VERSION", "0.0.0-dev")
GREETING = os.getenv("GREETING", "Hello from demo-api for rebiuld test")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

POD_NAME = os.getenv("POD_NAME", "local")
POD_IP = os.getenv("POD_IP", "127.0.0.1")
NODE_NAME = os.getenv("NODE_NAME", "local")
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    stream=sys.stdout,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","pod":"'
    + POD_NAME
    + '","msg":"%(message)s"}',
)
log = logging.getLogger("demo-api")

# -------------------------------------------------------------------- метрики
REQUESTS = Counter(
    "http_requests_total",
    "Всего HTTP-запросов",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Длительность обработки запроса",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
INFO = Gauge("app_info", "Метаданные приложения", ["version", "pod", "node"])
INFO.labels(version=VERSION, pod=POD_NAME, node=NODE_NAME).set(1)

INFLIGHT = Gauge("http_requests_in_flight", "Запросов обрабатывается сейчас")
ORDERS = Counter("demo_orders_total", "Бизнес-метрика: обработано заказов", ["status"])

# ---------------------------------------------------------------- состояние
# ready переключается через /toggle-ready — нужно, чтобы на практике увидеть,
# как под выпадает из Endpoints сервиса, оставаясь при этом живым.
STATE = {"ready": True, "ballast": []}


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("demo-api %s started on pod %s (node %s)", VERSION, POD_NAME, NODE_NAME)
    yield
    log.info("demo-api shutting down")


app = FastAPI(title="demo-api", version=VERSION, lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    """Считает метрики по каждому запросу."""
    # Используем шаблон роута (/items/{id}), а не конкретный URL,
    # иначе получим взрыв кардинальности меток.
    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    start = time.perf_counter()
    INFLIGHT.inc()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        INFLIGHT.dec()
        elapsed = time.perf_counter() - start
        path = request.scope.get("route").path if request.scope.get("route") else path
        if path != "/metrics":
            LATENCY.labels(request.method, path).observe(elapsed)
            REQUESTS.labels(request.method, path, str(status)).inc()
    return response


@app.get("/")
async def root():
    """Главная — показывает, какой под ответил. Видно балансировку."""
    return {
        "greeting": GREETING,
        "version": VERSION,
        "pod": POD_NAME,
        "pod_ip": POD_IP,
        "node": NODE_NAME,
        "namespace": NAMESPACE,
    }


@app.get("/healthz")
async def healthz():
    """Liveness: жив ли процесс. Всегда 200, пока приложение не зависло."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness: готов ли принимать трафик."""
    if not STATE["ready"]:
        return JSONResponse({"status": "not ready"}, status_code=503)
    return {"status": "ready"}


@app.post("/toggle-ready")
async def toggle_ready():
    """Переключает готовность. Для эксперимента с Endpoints."""
    STATE["ready"] = not STATE["ready"]
    log.warning("readiness switched to %s", STATE["ready"])
    return {"ready": STATE["ready"]}


@app.get("/slow")
async def slow(ms: int = 1000):
    """Медленный ответ. Нужен, чтобы поднять p95 и зажечь алерт."""
    ms = max(0, min(ms, 30000))
    await asyncio.sleep(ms / 1000)
    return {"slept_ms": ms, "pod": POD_NAME}


@app.get("/burn")
async def burn(ms: int = 500):
    """Жжёт CPU в течение ms. Для проверки HPA по CPU."""
    ms = max(0, min(ms, 10000))
    deadline = time.perf_counter() + ms / 1000
    x = 0
    while time.perf_counter() < deadline:
        x += 1
    return {"iterations": x, "pod": POD_NAME}


@app.post("/order")
async def order(fail: bool = False):
    """Бизнес-ручка для метрики demo_orders_total."""
    if fail:
        ORDERS.labels(status="failed").inc()
        return JSONResponse({"status": "failed"}, status_code=500)
    ORDERS.labels(status="ok").inc()
    return {"status": "ok", "pod": POD_NAME}


@app.post("/leak")
async def leak(mb: int = 50):
    """Съедает память. Для демонстрации limits и OOMKilled."""
    mb = max(1, min(mb, 2048))
    STATE["ballast"].append(bytearray(mb * 1024 * 1024))
    total = sum(len(b) for b in STATE["ballast"]) // (1024 * 1024)
    log.warning("allocated %s MB, total %s MB", mb, total)
    return {"allocated_mb": mb, "total_mb": total}


@app.post("/crash")
async def crash():
    """Убивает процесс. Для наблюдения CrashLoopBackOff и restart count."""
    log.error("crash requested, exiting")
    os._exit(1)


@app.get("/metrics")
async def metrics():
    """Эндпоинт для Prometheus. Его будет скрейпить ServiceMonitor."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

