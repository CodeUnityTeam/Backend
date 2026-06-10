## Запуск проекта


1. **Настройка переменных окружения**:

Скопируйте пример файла окружения:  

```bash
cp .env.example .env
```

Отредактируйте `.env` по необходимости. Установите DB_MODE=local

2. **Запуск базы данных** (опционально, если используется Docker):

Убедитесь, что в `config/settings.py` используются переменные окружения из `.env`

```bash
docker-compose -f docker-compose.local.yaml up -d
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

5. **Проверьте статус контейнера**:  

```bash
docker-compose -f docker-compose.db.yaml ps
```

6. **Остановка базы данных**:
```bash
docker-compose -f docker-compose.db.yaml down
```

_Примечание: Для работы с базой данных убедитесь, что порт 5432 свободен._

[⬅ Назад на главную](../README.md)

