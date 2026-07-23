# Мониторинг (Prometheus + Grafana)

## Стек

```
Django (django-prometheus) → Prometheus → Grafana
```

- **django-prometheus** — экспорт метрик из Django (HTTP, БД, кэш, Python GC)
- **Prometheus** — сбор и хранение метрик
- **Grafana** — визуализация и дашборды

## Структура файлов

```
monitoring/
├── prometheus/
│   ├── prometheus.yml          # конфиг для локального запуска (Django на хосте)
│   ├── prometheus.prod.yml     # конфиг для продакшена (Django в контейнере)
│   └── rules/
│       └── django_alerts.yml   # правила алертинга (пустой, заполнить при необходимости)
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml  # подключение Grafana к Prometheus
│   │   └── dashboards/
│   │       └── dashboards.yml  # автозагрузка дашбордов
│   └── dashboards/
│       └── django_dashboard.json  # дашборд Django (ID 17658 с Grafana Labs)
```

## Переменные окружения (.env)

```ini
# Prometheus
PROMETHEUS_CONFIG_FILE=./monitoring/prometheus/prometheus.yml
# ./monitoring/prometheus/prometheus.prod.yml — для запуска внутри Docker

# Grafana
GRAFANA_HOST=127.0.0.1
GRAFANA_PORT=3000
GRAFANA_USER=admin
GRAFANA_PASSWORD=password
GRAFANA_ROOT_URL=http://localhost:8080/grafana/
# http://localhost:3000/ — при прямом доступе (без nginx)
```

## Запуск

### Локально (Django на хосте, Prometheus/Grafana в Docker)

```bash
# 1. Добавить host.docker.internal в ALLOWED_HOSTS в .env:
#    ALLOWED_HOSTS=127.0.0.1,localhost,host.docker.internal

# 2. Запустить Prometheus и Grafana
docker compose -f docker-compose.local.yaml up -d prometheus grafana
```

### В контейнерах (dev / test / production)

```bash
# В .env указать:
# PROMETHEUS_CONFIG_FILE=./monitoring/prometheus/prometheus.prod.yml

# Запустить полный стек
docker compose -f docker-compose.dev.yaml up -d
```

## Доступ

| Сервис | Через nginx | Напрямую |
|--------|-------------|----------|
| **Grafana** | http://localhost:8080/grafana/ | http://localhost:3000 |
| **Prometheus** | — | http://localhost:9090 |

**Логин/пароль Grafana:** `admin` / `password` (из переменной `GRAFANA_PASSWORD`)

## Дашборды

### Django (ID 17658)

Дашборд скачан с [Grafana Labs](https://grafana.com/grafana/dashboards/17658) и автоматически загружается через provisioning.

**Панели:**
- **Requests** — количество запросов в секунду
- **2XX / 3XX / 4XX / 5XX Responses** — статусы ответов
- **DB Query Errors / DB Connection Errors** — ошибки БД
- **Cache Hit Ratio** — процент попаданий в кэш
- **Request Latency (p50 / p95 / p99)** — задержки запросов
- **Response Status** — график статусов по времени
- **Top 20 Views by Response Time** — самые медленные view
- **Top Requests** — самые популярные endpoint'ы
- **Database Total Queries / Query Duration** — метрики PostgreSQL

### Добавление нового дашборда

1. Скачать JSON-дашборд с Grafana Labs:
   ```bash
   curl -o monitoring/grafana/dashboards/new_dashboard.json \
     https://grafana.com/api/dashboards/<ID>/revisions/latest/download
   ```
2. Перезапустить Grafana:
   ```bash
   docker compose -f docker-compose.local.yaml restart grafana
   ```

## Метрики Django

Эндпоинт `/metrics` отдаёт метрики в формате Prometheus. Доступные группы:

| Группа | Префикс | Описание |
|--------|---------|----------|
| **HTTP** | `django_http_requests_*` | Количество, latency, размер запросов/ответов |
| **HTTP by view** | `django_http_requests_total_by_view_*` | Статистика по view и методам |
| **HTTP by status** | `django_http_responses_total_by_status_*` | Статистика по HTTP-статусам |
| **Database** | `django_db_*` | Количество запросов, длительность, ошибки |
| **Cache** | `django_cache_*` | Хиты/миссы, операции с кэшем |
| **Models** | `django_model_*` | INSERT/UPDATE/DELETE по моделям |
| **Migrations** | `django_migrations_*` | Применённые миграции |
| **Python GC** | `python_gc_*` | Сборка мусора |

## Переключение между окружениями

### Prometheus target

В [`prometheus.yml`](../monitoring/prometheus/prometheus.yml) target зависит от того, где запущен Django:

| Файл | Target | Когда использовать |
|------|--------|-------------------|
| `prometheus.yml` | `host.docker.internal:8000` | Django на хосте (локально) |
| `prometheus.prod.yml` | `backend:8000` | Django в Docker-контейнере |

Переключение через переменную `PROMETHEUS_CONFIG_FILE` в `.env`.

### Grafana root URL

| Значение | Когда использовать |
|----------|-------------------|
| `http://localhost:8080/grafana/` | Доступ через nginx (по умолчанию) |
| `http://localhost:3000/` | Прямой доступ (без nginx) |

Переключение через переменную `GRAFANA_ROOT_URL` в `.env`.

## Алертинг (не реализован - заготовка на будущее)

Используется для быстрого оповещения инженеров о проблемах,
предотвращения сбоев и сокращения времени простоя систем
(мессенджеры, email, системы дежурств)


Файл [`monitoring/prometheus/rules/django_alerts.yml`](../monitoring/prometheus/rules/django_alerts.yml) пуст. Для настройки алертов:

1. Добавить правила в `django_alerts.yml`
2. Подключить файл в конфиге Prometheus:
   ```yaml
   rule_files:
     - 'rules/django_alerts.yml'
   ```
3. Настроить контакты для уведомлений в Grafana (Alerting → Contact points)

## Docker Compose файлы

| Файл | Prometheus target | Grafana root | Назначение |
|------|-------------------|--------------|------------|
| `docker-compose.local.yaml` | `prometheus.yml` | Через nginx | Prometheus + Grafana отдельно |
| `docker-compose.local.full.yaml` | `prometheus.yml` | Через nginx | Полный локальный стек |
| `docker-compose.dev.yaml` | `prometheus.prod.yml` | Через nginx | Dev-окружение |
| `docker-compose.test.yaml` | `prometheus.prod.yml` | Через nginx | Тестовое окружение |