## Разработка

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
        data = (
            Collect.objects
            .select_related('author')
            .prefetch_related('payments__user')
            .annotate(
                current_price=Coalesce(Sum('payments__amount'), 0),
                donators_count=Count('payments__user', distinct=True),
            )
            .get(id=id)
        )
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