from typing import Any

from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# Импортируем сам модуль настроек, а не его содержимое через звездочку
from config import settings

# 1. Запускаем изолированный Postgres в Docker
postgres_container = PostgresContainer('postgres:16-alpine')
postgres_container.start()

# 2. Запускаем изолированный Redis в Docker
redis_container = RedisContainer('redis:7-alpine')
redis_container.start()

# 3. Копируем все настройки из основного файла в текущее пространство имен
globals().update(
    {
        key: getattr(settings, key)
        for key in dir(settings)
        if not key.startswith('__')
    },
)

# 4. Переопределяем параметры подключения к СУБД
DATABASES: dict[str, Any] = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': postgres_container.get_container_host_ip(),
        'PORT': int(postgres_container.get_exposed_port(5432)),
        'NAME': postgres_container.dbname,
        'USER': postgres_container.username,
        'PASSWORD': postgres_container.password,
    },
}

# 5. Переопределяем настройки кэша для работы с тестовым Redis
CACHES: dict[str, Any] = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{redis_container.get_container_host_ip()}:'
                    f'{redis_container.get_exposed_port(6379)}/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
}
