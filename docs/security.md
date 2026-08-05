# Security

## <img width="50" src="https://raw.githubusercontent.com/marwin1991/profile-technology-icons/refs/heads/main/icons/postgresql.png" alt="PostgreSQL" title="PostgreSQL"/>

Для стабильной работы с БД в проекте используются настройки:

- CONN_MAX_AGE - определяет врямя жизни соединения с БД в секундах. Не даёт создавать тьму тьмущую соединений и поддерживает подключение к БД вместо открытия новых.
- connect_timeout - Таймаут подключения к БД в секундах.
- 'options': '-c statement_timeout=30000' - Запрещает выполнение любого SQL-запроса дольше 30 секунд.


## 🚍 Троттлинг

Для ограничения количества запросов к серверу задан класс UniversalRateThrottle, который в зависимости от юзера (аутентифицированного или неаутентифицированного) задаёт кол-во запросов (scope) из settings.py. При превышении лимита сработает исключение 429.
Ошибка пример:
```
{
  "detail": "Запрос был проигнорирован. Expected available in 32 seconds."
}
```
В settings.py scope задаётся через префиксы anon_ / user_. По умолчанию используется `scope = 'default'`.
Пример:
```
DEFAULT_THROTTLE_RATES = {
            'anon_default': '50/min',
            'user_default': '500/min',
            'anon_login': '5/min',
            'user_login': '5/min',
}
```

## Настройки безопасности
`SECURE_SSL_REDIRECT`  - перенаправляем HTTP‑запросы на HTTPS

`SECURE_PROXY_SSL_HEADER`  - определяем, что запрос пришёл по защищённому HTTPS‑соединению

`SESSION_COOKIE_SECURE`  - сессионные cookie только по HTTPS

`CSRF_COOKIE_SECURE`  - CSRF‑cookie только по HTTPS

`SECURE_HSTS_SECONDS`  - ходим на домен только по HTTPS указанное кол-во секунд.