# demo-api

Учебный сервис для DevOps-практики. Каждая ручка нужна под конкретный
сценарий Kubernetes — «лишних» здесь нет.

## Ручки

| Метод | Путь | Зачем нужна |
|---|---|---|
| GET | `/` | Отдаёт имя пода и версию. Видно балансировку и результат rolling update |
| GET | `/healthz` | Liveness-проба |
| GET | `/readyz` | Readiness-проба. Отдаёт 503, если готовность выключена |
| POST | `/toggle-ready` | Переключает готовность. Под остаётся живым, но выпадает из Endpoints |
| GET | `/slow?ms=1000` | Медленный ответ. Поднимает p95 → срабатывает алерт |
| GET | `/burn?ms=500` | Жжёт CPU. Для проверки HPA |
| POST | `/order?fail=false` | Бизнес-метрика `demo_orders_total` |
| POST | `/leak?mb=50` | Съедает память. Для демонстрации limits и OOMKilled |
| POST | `/crash` | Убивает процесс → CrashLoopBackOff |
| GET | `/metrics` | Метрики для Prometheus |

## Переменные окружения

| Переменная | Откуда приходит | По умолчанию |
|---|---|---|
| `APP_VERSION` | значение из values Helm-чарта | `0.0.0-dev` |
| `GREETING` | ConfigMap | `Hello from demo-api` |
| `LOG_LEVEL` | ConfigMap | `INFO` |
| `POD_NAME` | Downward API (`metadata.name`) | `local` |
| `POD_IP` | Downward API (`status.podIP`) | `127.0.0.1` |
| `POD_NAMESPACE` | Downward API (`metadata.namespace`) | `default` |
| `NODE_NAME` | Downward API (`spec.nodeName`) | `local` |

## Метрики

- `http_requests_total{method,path,status}` — счётчик запросов
- `http_request_duration_seconds{method,path}` — гистограмма латентности,
  из неё считается p95 через `histogram_quantile`
- `http_requests_in_flight` — сколько запросов обрабатывается прямо сейчас
- `demo_orders_total{status}` — бизнес-метрика
- `app_info{version,pod,node}` — метаданные, всегда равна 1

В метках используется **шаблон роута** (`/slow`), а не конкретный URL с
параметрами. Иначе каждый уникальный запрос породил бы новую временную
серию — это называется взрывом кардинальности и убивает Prometheus.

## Локальный запуск

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Тесты

```bash
pip install pytest httpx
python -m pytest tests/ -q
```

## Что писать в Dockerfile

Подсказки, а не готовое решение — Dockerfile за тобой:

- база `python:3.12-slim`, multi-stage: зависимости ставим в builder,
  в рантайм копируем только нужное
- `PYTHONUNBUFFERED=1`, иначе логи будут застревать в буфере и не попадут
  в `kubectl logs`
- непривилегированный пользователь (`USER 1000`) — потребуется для
  `securityContext.runAsNonRoot`
- слой с `requirements.txt` копируем **до** кода приложения, чтобы кэш
  не инвалидировался при каждом изменении `main.py`
- `EXPOSE 8000`
- запуск: `uvicorn main:app --host 0.0.0.0 --port 8000`
