# Кэширование

Кэширование построено на **Redis** через `django-redis` с fallback на `LocMemCache`. При отказе Redis приложение продолжает работать без кэша (`DJANGO_REDIS_IGNORE_EXCEPTIONS = True`).

## Стек

- **Бэкенд:** `django_redis.cache.RedisCache`
- **Fallback:** `django_redis.cache.backends.locmem.LocMemCache`
- **Инвалидация по паттерну:** `cache.delete_pattern()` — Redis SCAN

## Паттерны кэширования

### 1. `CacheRetrieveMixin` — для детальных страниц

Файл: [`core/cache_mixins.py`](../core/cache_mixins.py)

Миксин для ViewSet'ов, кэширующий результат `retrieve()`.

**Ключ:** `{prefix}:detail:{lookup_value}:{user_id}`

Каждый пользователь имеет **свой кэш**, поэтому персонализированные поля (`is_liked_by_me`, `is_participant`, `is_liked`) сохраняются как есть — они всегда актуальны для конкретного пользователя.

**Используется в:**
- `ProjectViewSet` — `projects:detail:{project_id}:{user_id}`, TTL 10 мин
- `QuestionViewSet` — `qna:detail:{pk}:{user_id}`, TTL 5 мин
- `UserProfileView` — `users:detail:{user_id}:{user_id}`, TTL 10 мин

### 2. Ручное кэширование списков

Паттерн cache-aside: читаем из кэша, если нет — вычисляем и сохраняем.

**Ключ:** `{prefix}:list:{user_id?}:{md5(query_params)}`

- `user_id` добавляется, если данные персонализированы (список проектов, профилей)
- `user_id` **не** добавляется, если данные публичные (список вопросов)

**Где используется:**
- [`ProjectViewSet.list`](../projects/views/project.py:278) — `projects:list:{user_id}:{md5}`, TTL 5 мин
- [`QuestionViewSet.list`](../qna/views/question.py:68) — `qna:list:{md5}`, TTL 3 мин
- [`UserProfileListView.list`](../users/views/profile.py:475) — `users:list:{user_id}:{md5}`, TTL 5 мин
- [`ResponseFeedViewSet.list`](../projects/views/response_project.py:118) — `responses:feed:{user_id}:{md5}`, TTL 3 мин

### 3. Ручное кэширование рекомендаций

**Ключ:** `projects:recommendations:{user_id}`, TTL 10 мин

Где: [`ProjectViewSet.recommendations`](../projects/views/project.py:515)

### 4. Ручное кэширование справочных данных

**Ключи:** `skills:list`, `specializations:list`, `work_formats:list`, TTL 1 час

Где: [`TagsListAPIView.list`](../help/views.py:128)

### 5. `@never_cache` — для приватных эндпоинтов

- `MeProfileView` — профиль текущего пользователя
- `ProfileLikeAPIView` — переключение лайка пользователю

## Инвалидация

Вся инвалидация — сигнальная, через `post_save`/`post_delete`.

### Принципы

1. **Точечная инвалидация (cache stampede prevention)** — при лайке/действии кэш сбрасывается **только для конкретного пользователя**, а не для всех. Например, `ProjectLike.post_save` удаляет `projects:list:{user_id}:*` — только для того, кто лайкнул. Остальные пользователи продолжают использовать свой кэш.
2. **Инвалидация по паттерну для всех** — когда меняются сами данные (а не отношение пользователя к ним), кэш сбрасывается для всех через `delete_pattern('{prefix}:detail:{id}:*')`. Например, при изменении названия проекта — все видят новое название.

### Сигналы

| Модель | Файл | Что инвалидирует |
|--------|------|-------------------|
| `Project` | [`projects/signals.py:16`](../projects/signals.py:16) | `projects:detail:{id}:*`, `projects:list:*`, `projects:recommendations:*` |
| `ProjectLike` | [`projects/signals.py:40`](../projects/signals.py:40) | `projects:detail:{id}:{user_id}`, `projects:list:{user_id}:*` |
| `Response` | [`projects/signals.py:67`](../projects/signals.py:67) | `responses:feed:{user_id}:*`, `responses:feed:{author_id}:*` |
| `ProjectParticipant` | [`projects/signals.py:96`](../projects/signals.py:96) | `projects:detail:{project_id}:*` |
| `Question` | [`qna/signals.py:25`](../qna/signals.py:25) | `qna:detail:{pk}:*`, `qna:list:*` |
| `Answer` | [`qna/signals.py:39`](../qna/signals.py:39) | `qna:detail:{question_id}:*` |
| `QuestionLike` | [`qna/signals.py:52`](../qna/signals.py:52) | `qna:detail:{question_id}:{user_id}`, `qna:list:*` |
| `AnswerLike` | [`qna/signals.py:74`](../qna/signals.py:74) | `qna:detail:{answer.question_id}:{user_id}` |
| `User` | [`users/signals.py:17`](../users/signals.py:17) | `users:detail:{user_id}:*`, `users:list:*`, `projects:recommendations:{user_id}` |
| `UserLike` | [`users/signals.py:44`](../users/signals.py:44) | `users:list:{employer_id}:*`, `users:detail:{worker_id}:{employer_id}` |
| `Skill` | [`help/signals.py:18`](../help/signals.py:18) | `skills:list` |
| `Specialization` | [`help/signals.py:28`](../help/signals.py:28) | `specializations:list` |
| `WorkFormat` | [`help/signals.py:38`](../help/signals.py:38) | `work_formats:list` |

## Конфигурация

Все TTL и префиксы ключей: [`core/constants/cache.py`](../core/constants/cache.py)

| Константа | Значение | Назначение |
|-----------|----------|------------|
| `TAGS_CACHE_TIMEOUT` | 3600 (1 час) | Справочные данные |
| `PROJECT_LIST_CACHE_TIMEOUT` | 300 (5 мин) | Список проектов |
| `PROJECT_DETAIL_CACHE_TIMEOUT` | 600 (10 мин) | Детали проекта |
| `PROJECT_RECOMMENDATIONS_CACHE_TIMEOUT` | 600 (10 мин) | Рекомендации |
| `QUESTION_LIST_CACHE_TIMEOUT` | 180 (3 мин) | Список вопросов |
| `QUESTION_DETAIL_CACHE_TIMEOUT` | 300 (5 мин) | Детали вопроса |
| `USER_PROFILE_CACHE_TIMEOUT` | 600 (10 мин) | Профиль пользователя |
| `USER_PROFILE_LIST_CACHE_TIMEOUT` | 300 (5 мин) | Список профилей |
| `RESPONSE_FEED_CACHE_TIMEOUT` | 180 (3 мин) | Лента откликов |

## Кэширование изображений

Изображения (аватары, изображения вопросов/ответов, feedback) хранятся в **MinIO/S3** и кэшируются на уровне браузера. Redis для них не используется.

### Cache-Control на уровне S3

Файл: [`core/s3_utils.py:44`](../core/s3_utils.py:44)

При инициализации `MinioService` всем загружаемым файлам устанавливается заголовок:

```
Cache-Control: public, max-age=31536000, immutable
```

- `public` — разрешает кэширование прокси и CDN
- `max-age=31536000` — 1 год браузерного кэша
- `immutable` — файл никогда не меняется по одному URL

Это возможно, потому что каждый файл получает **UUID в имени** (`uuid4().hex`). Новый файл = новый URL, старый URL остаётся в кэше браузера навсегда. При обновлении изображения старый файл удаляется из MinIO, а в БД сохраняется новый URL.

### Удаление файлов при удалении записи

При удалении записи, ссылающейся на файл, файл физически удаляется из MinIO через сигналы `post_delete`. Удаление выполняется в `transaction.on_commit()` — только после успешного коммита транзакции БД, чтобы файл не был удалён при откате транзакции.

| Сигнал | Файл | Действие |
|--------|------|----------|
| `QuestionImage.post_delete` | [`qna/signals.py:93`](../qna/signals.py:93) | Удаляет файл из MinIO |
| `AnswerImage.post_delete` | [`qna/signals.py:107`](../qna/signals.py:107) | Удаляет файл из MinIO |
| `FeedbackImage.post_delete` | [`qna/signals.py:121`](../qna/signals.py:121) | Удаляет файл из MinIO |
| `User.post_delete` | [`qna/signals.py:135`](../qna/signals.py:135) | Удаляет аватар из MinIO |