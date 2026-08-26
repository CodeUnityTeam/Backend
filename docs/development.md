## Разработка

### Скопируй и вставь в терминал для локального тестирования перед PR

Обязательно включен локальный стек, миграции и теги в отдельном терминале
```bash
bash fixtures/test_data/create_users.sh
bash fixtures/test_data/create_obj.sh
```
теперь можно очистить и оставить админа
```bash
uv run python manage.py flush --noinput
DJANGO_SUPERUSER_PASSWORD=admin uv run python manage.py createsuperuser --email admin@example.com --first_name Admin --last_name Admin --noinput
```
скопируй для быстрого старта локалки, чтобы пройти тесты, если не запущен локально, потом вставь первый кусок выше
```
docker compose -f docker-compose.local.yaml up -d
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py loaddata fixtures/tags/*
uv run python manage.py runserver
```

#### Запуск на dev-сервере

На сервере используется [`load_on_dev.sh`](../fixtures/test_data/load_on_dev.sh), который сам подставляет нужные переменные:

```bash
sudo docker compose -f docker-compose.dev.yaml exec backend bash fixtures/test_data/load_on_dev.sh
```

Скрипт автоматически:
1. Регистрирует пользователей через API `https://dev.code-unity.ru/api/v1`
2. Подтверждает email через `python manage.py shell`
3. Создаёт проекты, вопросы, ответы и остальные тестовые данные

При необходимости можно переопределить переменные:

```bash
sudo docker compose -f docker-compose.dev.yaml exec \
  -e BASE_URL="https://custom.domain/api/v1" \
  backend bash fixtures/test_data/load_on_dev.sh
```
---

### Добавление зависимостей для разработки

Используйте опциональную группу `dev`:

```bash
uv add --group dev pytest ruff flake8
```

### Форматирование кода

Проект настроен с использованием `ruff`. Для проверки и автоматического исправления:

```bash
uv run ruff check --fix .
```

### Проверка типов:

```bash
uv run mypy .
```

### Тестирование:

```bash
uv run pytest
```

### Структура Django приложения

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

[⬅ Назад на главную](../README.md)