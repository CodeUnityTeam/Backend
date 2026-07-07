# CodeUnity
Скопируй и вставь в терминал для локального тестирования перед PR
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

### Backend

* [Зависимости](docs/requirements.md)
* [Запуск проекта](docs/start.md)
* [Разработка](docs/development.md)
* [Авторизация](docs/auth.md)
* [Наполнение БД](docs/add_tags.md)
* [Docker](docs/docker.md)
* [Admin-панель](docs/admin.md)
### Разделы
* [👤 Пользователи и профили](docs/users.md)
* [📁 Проекты](docs/projects.md)
* [❓ Вопросы и ответы (Q&A)](docs/qna.md)
* [☁️ Хранилище S3 Minio](docs/s3_minio.md)
* [⚡ Кэширование](docs/caching.md)


### Дополнительные ресурсы

- [Документация uv](https://docs.astral.sh/uv/)
- [Документация Django](https://docs.djangoproject.com/)
- [Документация Django REST Framework](https://www.django-rest-framework.org/)
