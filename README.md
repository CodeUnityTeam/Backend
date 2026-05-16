###### Backend

Проект использует **uv** — быстрый менеджер пакетов Python.

#### Установка uv

Если uv не установлен глобально:

```bash

# Установка зависимостей через uv
```
[Справка](https://habr.com/ru/articles/875840)


```bash
pip install uv
```

#### Инициализация проекта с uv

Проект уже содержит `pyproject.toml` с зависимостями. Для начала работы:

1. **Создание виртуального окружения** (если ещё не создано):

```bash
uv venv .venv --python 3.12
```

2. **Активация окружения**:

```bash
source .venv/bin/activate
```

3. **Установка зависимостей**:

```bash
uv pip install -e .
```

Или просто (uv автоматически использует виртуальное окружение):

```bash
uv sync --all-extras
```

#### Управление зависимостями

- **Добавить новую зависимость**:

```bash
uv add package-name
```

- **Удалить зависимость**:

```bash
uv remove package-name
```

- **Обновить все зависимости**:

```bash
uv pip compile --upgrade
```

#### Запуск проекта

1. **Настройка переменных окружения**:

Скопируйте пример файла окружения:

```bash
cp .env.example .env
```

Отредактируйте `.env` по необходимости.

2. **Запуск базы данных** (опционально, если используется Docker):

```bash
docker-compose -f docker-compose.db.yaml up -d
```

3. **Применение миграций**:

```bash
python manage.py migrate
```

4. **Запуск сервера разработки**:

```bash
python manage.py runserver
```

Или с использованием gunicorn (для продакшена):

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### Разработка

#### Добавление зависимостей для разработки

Используйте опциональную группу `dev`:

```bash
uv add --group dev pytest ruff flake8
```

#### Форматирование кода

Проект настроен с использованием `ruff`:

```bash
uv run ruff check .
```

#### Проверка типов

```bash
uv run mypy .
```

#### Тестирование

```bash
uv run pytest
```

#### Миграция с requirements.txt

Если вы ранее использовали `requirements.txt`, зависимости уже перенесены в `pyproject.toml`. Вы можете продолжать использовать `requirements.txt` для совместимости, но рекомендуется перейти на `pyproject.toml`.

Для генерации `requirements.txt` из `pyproject.toml`:

```bash
uv pip compile -o requirements.txt pyproject.toml
```

#### Полезные команды uv

- `uv python` — запуск Python с активированным окружением
- `uv run` — запуск команды в виртуальном окружении
- `uv pip list` — список установленных пакетов
- `uv pip freeze` — вывод зависимостей в формате requirements
- `uv pip compile` — компиляция зависимостей с разрешением версий

#### Запуск только базы данных для разработки

Если вы хотите работать с локальным Django-приложением, но использовать контейнеризованную базу данных:

1. Запустите только базу данных:
```bash
docker-compose -f docker-compose.db.yaml up -d
```

2. Проверьте статус контейнера:
```bash
docker-compose -f docker-compose.db.yaml ps
```

3. Настройте Django для подключения к базе данных:
   - Убедитесь, что в `config/settings.py` используются переменные окружения из `.env`
   - Выполните миграции:
```bash
python manage.py migrate
```

4. Остановка базы данных:
```bash
docker-compose -f docker-compose.db.yaml down
```

> Примечание: Для работы с базой данных убедитесь, что порт 5432 свободен.

#### Структура Django приложения

Здесь создано базовое приложение config для запуска.
Создать новое приложение можно командой `django startapp <app_name>`

- Можно пойти через создание приложения api/ и писать там весь функционал бекенда.
- Можно создавать отдельные приложения и работать в них.

Общая структура Django приложения (для пользователей или вопросов или проектов):
```
<app_name>/
    __init__.py
    admin.py
    apps.py
    models.py
    serializers.py
    views.py
    selectors.py
    services.py
```

Основная идея в том, что мы выносим запросы отдельным файлом и добавляем во views.py
Бизнес-логику выносим в отдельный файл, например, services.py
Здесь происходит создание, валидация данных, отправка почты.

#### Примеры

**selectors.py** - отдельно для построения запросов, пример (здесь обработка запроса):
```python
def collect_detail(id):
    """Получение детальной информации о сборе."""
    cache_data = cache_collect_detail(id)
    if cache_data is not None:
        return cache_data
    try:
        data = Collect.objects.select_related('author').prefetch_related(
            'payments__user').annotate(
            current_price=Coalesce(Sum('payments__amount'), 0),
            donators_count=Count('payments__user', distinct=True),
        ).get(id=id)
        cache_collect_detail(id, data)
        return data
    except Collect.DoesNotExist:
        raise Http404('Сбор не найден')
```

**services.py** - отдельно для логики приложения, пример (здесь сервис кеширует данные и отправляет почту):
```python
@transaction.atomic
def collect_create(collect_data) -> Collect:
    """Создание нового сбора."""
    collect = Collect(**collect_data)
    collect.full_clean()
    collect.save()
    send_collect_created_email(collect)
    invalidate_collect_list_cache()
    return collect
```

## Дополнительные ресурсы

- [Документация uv](https://docs.astral.sh/uv/)
- [Документация Django](https://docs.djangoproject.com/)
- [Документация Django REST Framework](https://www.django-rest-framework.org/)
