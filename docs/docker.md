# Docker

Проект использует Docker для изолированного запуска сервисов и развёртывания.

### Локальная разработка (`docker-compose.local.yaml`)

Запускает PostgreSQL и MinIO, чтобы не устанавливать их локально. Django запускается отдельно через `runserver`.

```bash
docker-compose -f docker-compose.local.yaml up -d
```

### Развёртывание на сервере (`docker-compose.dev.yaml`)
Запускает backend, БД, MinIO и Nginx. Используется на сервере.
```bash
docker-compose -f docker-compose.dev.yaml up -d
```

### CI/CD
При пуше в main GitHub Actions собирает образ backend, пушит в DockerHub и деплоит на сервер через `docker-compose.dev.yaml`.

[⬅ Назад на главную](../README.md)
