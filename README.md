# CodeUnity
Скопируй и вставь в терминал для локального тестирования перед PR
Обязательно включен локальный стек, миграции и теги
```bash
bash fixtures/test_data/create_users.sh
bash fixtures/test_data/create_obj.sh
```
скопируй для быстрого старта локалки, чтобы пройти тесты, если не запущен локально, потом вставь первый кусок выше
```
docker compose -f docker-compose.local.yaml up -d
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py loaddata fixtures/tags/*
```
---

### Backend

* [Зависимости](docs/requirements.md)
* [Запуск проекта](docs/start.md)
* [Разработка](docs/development.md)
* [Авторизация](docs/auth.md)
* [Наполнение БД](docs/add_tags.md)
* [Docker](docs/docker.md)
### Разделы
* [👤 Пользователи и профили](docs/users.md)
* [📁 Проекты](docs/projects.md)
* [❓ Вопросы и ответы (Q&A)](docs/qna.md)
* [☁️ Хранилище S3 Minio](docs/s3_minio.md)


### Дополнительные ресурсы

- [Документация uv](https://docs.astral.sh/uv/)
- [Документация Django](https://docs.djangoproject.com/)
- [Документация Django REST Framework](https://www.django-rest-framework.org/)
