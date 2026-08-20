# Хранилище S3 (MinIO)

В проекте используется объектное хранилище S3 (на базе MinIO) для хранения всех медиафайлов: аватаров, изображений к вопросам, ответам, проектам и формам обратной связи.

## Архитектура

Для взаимодействия с S3 реализован единый сервис [`S3Service`](../minio/s3_utils.py). Он автоматически:
- Создаёт бакеты при первом обращении, если они отсутствуют.
- Выполняет загрузку и удаление объектов.
- Генерирует presigned URL для прямой загрузки с фронтенда.

### Типы медиа и бакеты

Каждый тип контента хранится в отдельном бакете. Маппинг задаётся в [`MediaType`](../core/s3_utils.py:12) (enum) и [`S3_BUCKETS`](../config/settings.py:129) (настройки):

| MediaType | Ключ `S3_BUCKETS` | Бакет (по умолчанию) | Префикс |
|---|---|---|---|
| `AVATAR` | `avatars` | `user-avatars` | `avatars/` |
| `QUESTION_IMAGE` | `questions` | `question-images` | `questions/` |
| `ANSWER_IMAGE` | `answers` | `answer-images` | `answers/` |
| `FEEDBACK_IMAGE` | `feedback` | `feedback-images` | `feedback/` |
| `PROJECT_IMAGE` | `projects` | `project-images` | `projects/` |
| `UPLOAD_IMAGE` | `images` | `upload-images` | `images/` |

Имена бакетов настраиваются через переменные окружения (см. `.env.example`). Ключи словаря `S3_BUCKETS` **обязаны** совпадать со значениями `MediaType`.

### Использование

```python
from minio.s3_utils import S3Service, MediaType

# Загрузка файла
url = S3Service.upload(MediaType.AVATAR, file_obj)

# Удаление файла
S3Service.delete(MediaType.AVATAR, url)

# Presigned URL для прямой загрузки
result = S3Service.generate_presigned_upload_url(
    MediaType.UPLOAD_IMAGE, 'photo.jpg', expires_in=3600,
)
# result = { 'url': ..., 'object_key': ..., 'public_url': ... }
```

## Конфигурация

Настройки S3 находятся в [`config/settings.py`](../config/settings.py:115):

```python
# Эндпоинт MinIO (внутренний, для Django)
S3_ENDPOINT = os.getenv('S3_ENDPOINT_URL', 'http://minio:9000')

# Публичный URL для доступа браузера (через nginx)
S3_PUBLIC_URL = os.getenv('S3_PUBLIC_URL', '').rstrip('/')

# Кастомный домен для публичных URL (без протокола)
S3_CUSTOM_DOMAIN = (
    S3_PUBLIC_URL.replace('http://', '').replace('https://', '')
    if S3_PUBLIC_URL
    else S3_ENDPOINT.replace('http://', '').replace('https://', '')
)

# Имена бакетов для каждого типа медиа
S3_BUCKETS = {
    'avatars': os.getenv('AVATARS_BUCKET', 'user-avatars'),
    'questions': os.getenv('QUESTION_IMAGES_BUCKET', 'question-images'),
    'answers': os.getenv('ANSWER_IMAGES_BUCKET', 'answer-images'),
    'feedback': os.getenv('FEEDBACK_IMAGES_BUCKET', 'feedback-images'),
    'projects': os.getenv('PROJECT_IMAGES_BUCKET', 'project-images'),
    'images': os.getenv('UPLOAD_IMAGES_BUCKET', 'upload-images'),
}

# Максимальный размер файла (в MB)
S3_MAX_FILE_SIZE_MB = 10
```

### Как формируется публичный URL

1. Если задан `S3_PUBLIC_URL` (например, `https://dev.code-unity.ru/media`), то `S3_CUSTOM_DOMAIN = dev.code-unity.ru/media`.
2. Иначе `S3_CUSTOM_DOMAIN` берётся из `S3_ENDPOINT_URL` без протокола.
3. В `S3Service._init_storage` к домену добавляется имя бакета: `f'{custom_domain}/{bucket_name}'`.

Таким образом, URL файла выглядит как:
- **Локально**: `http://localhost:9000/upload-images/images/uuid.jpg`
- **Продакшен**: `https://dev.code-unity.ru/media/upload-images/images/uuid.jpg`

## Общий флоу работы с изображениями

Для минимизации нагрузки на основную БД используется двухэтапная загрузка:

1. **Upload**: Файл загружается через `POST /api/v1/qna/files/upload/`. Сервис возвращает публичный `image_url` и метаданные (имя, размер, тип).
2. **Attach**: Полученные данные передаются фронтендом в основные эндпоинты (создание вопроса, профиля и т.д.). В базе сохраняются только метаданные и ссылка.

## Автоматическое управление файлами

Для поддержания чистоты хранилища реализована автоматизация удаления:

- **Сигналы (`post_delete`)**: При удалении записи из БД (даже каскадном), физический файл автоматически удаляется из MinIO. Обработчики в [`qna/signals.py`](../qna/signals.py).
- **Транзакционность**: Удаление файлов происходит только после успешного коммита транзакции в БД (`transaction.on_commit`).
- **Замена файлов**: При обновлении аватара старый файл удаляется, освобождая место (см. [`avatar_upload_handler`](../users/services.py:20)).

## Очистка сиротских файлов

Если файл был загружен в S3, но не привязан к записи в БД (например, пользователь загрузил изображение, но не завершил создание вопроса), он считается «сиротой».

Для очистки используется management command:

```bash
# Сухой прогон (только показать, что будет удалено)
python manage.py cleanup_s3_orphans --dry-run

# Принудительное удаление
python manage.py cleanup_s3_orphans --force
```

Команда итерируется по всем [`MediaType`](../core/s3_utils.py:12), собирает URL из БД и сверяет с объектами в S3. Несовпадающие удаляет.

## Доступ к хранилищу (локально)

- **API**: `http://localhost:9000`
- **Консоль управления**: `http://localhost:9001` (логин/пароль из `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` в `.env`)

## Публичные URL (продакшен)

В продакшене nginx проксирует `/media/` на MinIO:

```
Фронтенд → https://dev.code-unity.ru/media/user-avatars/avatars/uuid.jpg
         → nginx (location /media/)
         → http://minio:9000/user-avatars/avatars/uuid.jpg
```

Настройка `S3_PUBLIC_URL=https://dev.code-unity.ru/media` в `.env` гарантирует, что в БД сохраняются публичные URL, доступные из браузера.

[⬅ Назад на главную](../README.md)