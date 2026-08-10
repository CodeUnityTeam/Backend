# Логирование

Логирование построено на стандартном модуле `logging` из Python. Конфигурация задаётся через `dictConfig` в [`config/settings.py`](../config/settings.py:432).

## Стек

- **Модуль:** `logging` (стандартная библиотека Python)
- **Конфигурация:** `logging.config.dictConfig` — словарь в `settings.py`
- **Форматтеры:** `simple` (консоль) и `detailed` (файл)
- **Хэндлеры:** `StreamHandler` (консоль) и `MakeDirRotatingFileHandler` (файл с ротацией)
- **Фильтры:** `ParentDirFilter` — добавляет имя каталога исходного кода в запись

## Конфигурация

### Кастомные классы

#### `MakeDirRotatingFileHandler`

Файл: [`config/settings.py`](../config/settings.py:437)

Хэндлер на основе `RotatingFileHandler`, который **автоматически создаёт директорию для логов** перед инициализацией файла. Это избавляет от необходимости вручную создавать папку `logs/`.

```python
class MakeDirRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Хэндлер, создающий папку для логов перед инициализацией."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        filename = kwargs.get('filename', args[0] if args else '')
        log_dir = os.path.dirname(str(filename))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        super().__init__(*args, **kwargs)
```

#### `ParentDirFilter`

Файл: [`config/settings.py`](../config/settings.py:451)

Фильтр, добавляющий в `LogRecord` атрибут `parent_dir` — имя каталога, в котором лежит исходный `.py` файл. Используется в `detailed`-форматтере для быстрой идентификации модуля.

```python
class ParentDirFilter(logging.Filter):
    """Фильтр для добавления имени каталога исходного кода в лог."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.pathname:
            record.parent_dir = os.path.basename(
                os.path.dirname(record.pathname),
            )
        else:
            record.parent_dir = ''
        return True
```

### Форматтеры

| Имя | Формат | Назначение |
|-----|--------|------------|
| `simple` | `%(asctime)s - %(levelname)s - [%(name)s] - %(message)s` | Консоль |
| `detailed` | `%(asctime)s - [%(levelname)s] - %(name)s %(parent_dir)s/%(filename)s:%(funcName)s:%(lineno)d - %(message)s` | Файл |

Пример записи в `detailed`-формате:

```
2026-07-21 19:17:25 - [WARNING] - projects signals/projects.py:update_project_cache_on_change:42 - Ключ кэша projects:list:* инвалидирован
```

### Хэндлеры

| Имя | Класс | Уровень | Назначение |
|-----|-------|---------|------------|
| `console` | `logging.StreamHandler` | `DEBUG` | Вывод в stdout/stderr |
| `file` | `MakeDirRotatingFileHandler` | `WARNING` | Запись в `logs/logs.log` |

Параметры файлового хэндлера:

- **Файл:** `logs/logs.log` (относительно `BASE_DIR`)
- **Режим:** `a` (дозапись)
- **Кодировка:** `utf-8`
- **Максимальный размер:** 5 MB (`maxBytes = 5_242_880`)
- **Резервных копий:** 3 (`backupCount = 3`)
- **Фильтры:** `add_parent_dir`

### Логгеры приложений

Все логгеры приложений настроены на уровень `DEBUG` и пишут одновременно в консоль и файл:

| Логгер | Уровень | Хэндлеры | Пропагация |
|--------|---------|----------|------------|
| `core` | `DEBUG` | console, file | ❌ |
| `users` | `DEBUG` | console, file | ❌ |
| `projects` | `DEBUG` | console, file | ❌ |
| `qna` | `DEBUG` | console, file | ❌ |
| `feedback` | `DEBUG` | console, file | ❌ |
| `help` | `DEBUG` | console, file | ❌ |

### Системные логгеры Django

| Логгер | Уровень | Хэндлеры | Пропагация |
|--------|---------|----------|------------|
| `django.request` | `ERROR` | file | ❌ |
| `django.db.backends` | `ERROR` | file | ❌ |
| `django.security` | `WARNING` | file | ❌ |

### Корневой логгер

```python
'root': {
    'level': 'WARNING',
    'handlers': ['console', 'file'],
}
```

Все логгеры, не указанные явно, наследуют корневой логгер с уровнем `WARNING`.

## Использование в коде

Во всех модулях логгер создаётся стандартным способом:

```python
import logging

logger = logging.getLogger(__name__)
```

Благодаря настройке логгеров по имени приложения (`core`, `users`, `projects`, `qna`, `feedback`, `help`), вызов `logging.getLogger(__name__)` автоматически подхватывает правильную конфигурацию. Например, для файла `projects/services.py` логгером будет `projects.services`, который наследует настройки логгера `projects`.

### Примеры использования

```python
# projects/services.py
logger = logging.getLogger(__name__)

def create_project(...):
    logger.debug('Создание проекта с данными: %s', data)
    # ...
    logger.info('Проект %s создан пользователем %s', project.id, user.id)
```

```python
# core/cache_mixins.py
logger = logging.getLogger(__name__)

def invalidate_cache(...):
    logger.warning('Ключ кэша %s инвалидирован', cache_key)
```

## Где используются логгеры

Логгеры инициализированы во всех ключевых модулях проекта:

- [`core/cache_mixins.py`](../core/cache_mixins.py) — кэширование
- [`core/exceptions.py`](../core/exceptions.py) — исключения
- [`core/parsers.py`](../core/parsers.py) — парсеры
- [`../minio/s3_utils.py`](../minio/s3_utils.py) — S3
- [`core/management/commands/cleanup_s3_orphans.py`](../core/management/commands/cleanup_s3_orphans.py) — команда очистки S3
- [`documents/views.py`](../documents/views.py) — документы
- [`feedback/serializers.py`](../feedback/serializers.py) — сериализаторы фидбека
- [`feedback/views.py`](../feedback/views.py) — вьюхи фидбека
- [`help/signals.py`](../help/signals.py) — сигналы помощи
- [`help/views.py`](../help/views.py) — вьюхи помощи
- [`projects/selectors.py`](../projects/selectors.py) — селекторы проектов
- [`projects/serializers/project.py`](../projects/serializers/project.py) — сериализаторы проектов
- [`projects/serializers/response_project.py`](../projects/serializers/response_project.py) — сериализаторы откликов
- [`projects/services.py`](../projects/services.py) — сервисы проектов
- [`projects/signals.py`](../projects/signals.py) — сигналы проектов
- [`projects/views/project.py`](../projects/views/project.py) — вьюхи проектов
- [`projects/views/response_project.py`](../projects/views/response_project.py) — вьюхи откликов
- [`qna/serializers/answer.py`](../qna/serializers/answer.py) — сериализаторы ответов
- [`qna/services.py`](../qna/services.py) — сервисы Q&A
- [`qna/signals.py`](../qna/signals.py) — сигналы Q&A
- [`qna/views/answer.py`](../qna/views/answer.py) — вьюхи ответов
- [`qna/views/file.py`](../qna/views/file.py) — вьюхи файлов
- [`qna/views/question.py`](../qna/views/question.py) — вьюхи вопросов
- [`users/middleware.py`](../users/middleware.py) — middleware
- [`users/serializers/auth.py`](../users/serializers/auth.py) — сериализаторы аутентификации
- [`users/services.py`](../users/services.py) — сервисы пользователей
- [`users/signals.py`](../users/signals.py) — сигналы пользователей
- [`users/views/auth.py`](../users/views/auth.py) — вьюхи аутентификации
- [`users/views/profile.py`](../users/views/profile.py) — вьюхи профиля

## Уровни логирования

| Уровень | Значение | Где используется |
|---------|----------|------------------|
| `DEBUG` | 10 | Детальная отладочная информация (параметры запросов, данные) |
| `INFO` | 20 | Информационные сообщения (создание объекта, успешная операция) |
| `WARNING` | 30 | Предупреждения (устаревший кэш, нештатная ситуация) |
| `ERROR` | 40 | Ошибки (исключения, сбой операции) |
| `CRITICAL` | 50 | Критические ошибки (приложение не может продолжить работу) |

## Ротация логов

Файловый хэндлер использует ротацию по размеру:

- Максимальный размер одного файла: **5 MB**
- Количество резервных копий: **3**
- Формат имени при ротации: `logs.log`, `logs.log.1`, `logs.log.2`, `logs.log.3`

При достижении 5 MB текущий файл закрывается и переименовывается в `logs.log.1`, старый `logs.log.1` — в `logs.log.2` и т. д. Самый старый файл удаляется.

## Лучшие практики

1. **Используйте `__name__`** для получения логгера — это автоматически даёт правильное имя с учётом иерархии.
2. **Не используйте f-строки** в сообщениях логов — используйте `%s`-форматирование, чтобы строка вычислялась только при активированном уровне логирования:
   ```python
   # ✅ Правильно
   logger.debug('Пользователь %s выполнил действие %s', user.id, action)
   
   # ❌ Неправильно
   logger.debug(f'Пользователь {user.id} выполнил действие {action}')
   ```
3. **Выбирайте правильный уровень:** `DEBUG` для отладки, `INFO` для операций, `WARNING` для нештатных ситуаций, `ERROR` для сбоев.
4. **Не логируйте чувствительные данные:** пароли, токены, персональные данные пользователей.
5. **Добавляйте контекст:** логируйте ID объектов, имена операций — это упрощает поиск по логам.