# Кэширование

Кэширование построено на **Redis** через `django-redis` с fallback на `LocMemCache`. При отказе Redis приложение продолжает работать без кэша (`DJANGO_REDIS_IGNORE_EXCEPTIONS = True`).

## Стек

- **Бэкенд:** `django_redis.cache.RedisCache`
- **Fallback:** `django_redis.cache.backends.locmem.LocMemCache`
- **Инвалидация по паттерну:** `cache.delete_pattern()` — Redis SCAN
- **Счётчики:** `cache.incr()` / `cache.decr()` — атомарные операции Redis

## Паттерны кэширования

### 1. Счётчики в Redis (incr/decr)

Файл: [`core/cache_mixins.py`](../core/cache_mixins.py)

Агрегированные счётчики (лайки, участники) хранятся в Redis и обновляются атомарно через `incr`/`decr`. Это заменяет дорогие `Count`-аннотации в SQL-запросах.

**Ключи:**
- `counter:project:likes:{project_id}` — количество лайков проекта
- `counter:project:participants:{project_id}` — количество участников проекта

**Функции-хелперы:**
- `incr_counter(prefix, object_id)` — увеличить счётчик
- `decr_counter(prefix, object_id)` — уменьшить счётчик (не уходит в минус)
- `get_counter(prefix, object_id, default=0)` — прочитать счётчик
- `get_or_seed_counter(prefix, object_id, qs)` — прочитать счётчик, при отсутствии — подсчитать в БД и сохранить

**Обновление:** В сигналах `ProjectLike.post_save`/`post_delete` и `ProjectParticipant.post_save`/`post_delete` — `incr_counter()`/`decr_counter()`.

**Чтение:** В сериализаторах `ProjectShortSerializer`, `ProjectDetailSerializer`, `FeedbackAndInvitationFeedSerializer` — `get_or_seed_counter()` с fallback на БД.

**Преимущества:**
- Убирает `LEFT JOIN` + `GROUP BY` из каждого запроса списка/детальной страницы
- Счётчики обновляются атомарно, без сброса всего кэша
- При откате Redis — автоматический fallback на COUNT в БД

### 2. `CacheRetrieveMixin` — для детальных страниц

Файл: [`core/cache_mixins.py`](../core/cache_mixins.py)

Миксин для ViewSet'ов, кэширующий результат `retrieve()`.

**Ключ:** `{prefix}:detail:{lookup_value}:{user_id}`

Каждый пользователь имеет **свой кэш**, поэтому персонализированные поля (`is_liked_by_me`, `is_participant`, `is_liked`) сохраняются как есть — они всегда актуальны для конкретного пользователя.

**Используется в:**
- `ProjectViewSet` — `projects:detail:{project_id}:{user_id}`, TTL 10 мин
- `QuestionViewSet` — `qna:detail:{pk}:{user_id}`, TTL 5 мин
- `UserProfileView` — `users:detail:{user_id}:{user_id}`, TTL 10 мин

### 3. Кэширование IDs объектов (вместо полного JSON-ответа)

Паттерн cache-aside: в кэше хранятся только ID объектов (UUID), а сам queryset с prefetch_related строится заново. Это делает ответ независимым от изменений сериализаторов.

**Ключ:** `{prefix}:list:ids:{user_id?}:{md5(query_params)}`

- `user_id` добавляется, если данные персонализированы (список проектов, профилей)
- `user_id` **не** добавляется, если данные публичные (список вопросов)

**Где используется:**
- [`ProjectViewSet.list`](../projects/views/project.py:157) — `projects:list:ids:{user_id}:{md5}`, TTL 5 мин

**Преимущества:**
- Компактный кэш (только UUID, а не полный JSON)
- Независимость от изменений сериализаторов
- Данные всегда актуальны (кроме списка IDs)

### 4. Ручное кэширование списков (полный JSON)

Для списков, где частота изменений низкая или сериализаторы стабильны.

**Ключ:** `{prefix}:list:{user_id?}:{md5(query_params)}`

**Где используется:**
- [`QuestionViewSet.list`](../qna/views/question.py:68) — `qna:list:{md5}`, TTL 3 мин
- [`UserProfileListView.list`](../users/views/profile.py:475) — `users:list:{user_id}:{md5}`, TTL 5 мин
- [`ResponseFeedViewSet.list`](../projects/views/response_project.py:118) — `responses:feed:{user_id}:{md5}`, TTL 3 мин

### 5. Ручное кэширование рекомендаций

**Ключ:** `projects:recommendations:{user_id}`, TTL 10 мин

Где: [`ProjectViewSet.recommendations`](../projects/views/project.py:515)

### 6. Ручное кэширование справочных данных

**Ключи:** `skills:list`, `specializations:list`, `work_formats:list`, TTL 1 час

Где: [`TagsListAPIView.list`](../help/views.py:128)

### 7. `@never_cache` — для приватных эндпоинтов

- `MeProfileView` — профиль текущего пользователя
- `ProfileLikeAPIView` — переключение лайка пользователю

## Инвалидация

Вся инвалидация — сигнальная, через `post_save`/`post_delete`.

### Принципы

1. **Счётчики через incr/decr** — лайки и участники обновляются атомарно, без сброса кэша.
2. **Точечная инвалидация (cache stampede prevention)** — при лайке/действии кэш сбрасывается **только для конкретного пользователя**, а не для всех. Например, `ProjectLike.post_save` удаляет `projects:list:ids:{user_id}:*` — только для того, кто лайкнул. Остальные пользователи продолжают использовать свой кэш.
3. **Инвалидация по паттерну для всех** — когда меняются сами данные (а не отношение пользователя к ним), кэш сбрасывается для всех через `delete_pattern('{prefix}:detail:{id}:*')`. Например, при изменении названия проекта — все видят новое название.
4. **Минимизация избыточной инвалидации** — лайк вопроса не сбрасывает список вопросов (`qna:list:*`), т.к. не меняет состав списка. Инвалидация списка проектов при изменении проекта сужена до автора (`projects:list:{author_id}:*`).

### Сигналы

| Модель | Файл | Что инвалидирует |
|--------|------|-------------------|
| `Project` | [`projects/signals.py:16`](../projects/signals.py:16) | `projects:detail:{id}:*`, `projects:list:{author_id}:*`, `projects:recommendations:*` |
| `ProjectLike` | [`projects/signals.py:48`](../projects/signals.py:48) | `counter:project:likes:{id}` (incr/decr), `projects:detail:{id}:{user_id}`, `projects:list:{user_id}:*` |
| `Response` | [`projects/signals.py:93`](../projects/signals.py:93) | `responses:feed:{user_id}:*` (только автор отклика) |
| `ProjectParticipant` | [`projects/signals.py:108`](../projects/signals.py:108) | `counter:project:participants:{id}` (incr/decr), `projects:detail:{project_id}:*` |
| `Question` | [`qna/signals.py:28`](../qna/signals.py:28) | `qna:detail:{pk}:*`, `qna:list:*` |
| `Answer` | [`qna/signals.py:42`](../qna/signals.py:42) | `qna:detail:{question_id}:*` |
| `QuestionLike` | [`qna/signals.py:55`](../qna/signals.py:55) | `qna:detail:{question_id}:{user_id}` (список не инвалидируется) |
| `AnswerLike` | [`qna/signals.py:73`](../qna/signals.py:73) | `qna:detail:{answer.question_id}:{user_id}` |
| `User` | [`users/signals.py:17`](../users/signals.py:17) | `users:detail:{user_id}:*`, `users:list:*`, `projects:recommendations:{user_id}` |
| `UserLike` | [`users/signals.py:36`](../users/signals.py:36) | `users:list:{employer_id}:*`, `users:detail:{worker_id}:{employer_id}` |
| `Skill` | [`help/signals.py:16`](../help/signals.py:16) | `skills:list` |
| `Specialization` | [`help/signals.py:26`](../help/signals.py:26) | `specializations:list` |
| `WorkFormat` | [`help/signals.py:36`](../help/signals.py:36) | `work_formats:list` |

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
| `COUNTER_PROJECT_LIKES_PREFIX` | `counter:project:likes` | Префикс счётчика лайков проекта |
| `COUNTER_PROJECT_PARTICIPANTS_PREFIX` | `counter:project:participants` | Префикс счётчика участников проекта |

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