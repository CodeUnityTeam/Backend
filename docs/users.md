# Пользователи и профили

# API авторизации и пользователей

**Базовый URL:** `https://dev.code-unity.ru/api/v1/user/`

**Префикс:** `/api/v1/user/`

Сервис управления учетными записями, профилями разработчиков и их компетенциями.

### Возможности
- **Аутентификация**: JWT-токены и социальный вход (Yandex, Mail.ru).
- **Профили**: Публичные данные пользователей с полнотекстовым поиском по именам, городам и навыкам.
- **Навыки и Роли**: Связь со справочниками `Skill` и `Specialization`.

### Аватары
Профили поддерживают загрузку аватаров. Работа с файлами аватаров делегирована [S3 Minio](s3_minio.md). Реализовано автоматическое удаление старых аватаров при загрузке новых или удалении аккаунта.

## Профиль пользователя

### 1. Получить/редактировать свой профиль

**`GET /profile/me/`** — получить профиль
**`PATCH /profile/me/`** — частично обновить профиль

**Заголовок:** `Authorization: Bearer <access-токен>`

**Пример PATCH:**
```json
{
  "city": "Москва",
  "about_me": "Разработчик",
  "skills": [{"skill_id": "uuid-навыка"}],
  "specializations": [{"spec_id": "uuid-специализации"}],
  "workformats": [{"format_id": "uuid-формата"}]
}
```

**Ответ (200):** полный объект пользователя.

> **Поля профиля:** `first_name`, `last_name`, `phone_number`, `additional_contact`, `country`, `city`, `soft_skills`, `about_me`, `projects_relation`, `skills`, `specializations`, `workformats`, `experiences`. Email и role — read-only.

### 2. Удалить аккаунт (мягкое удаление)

**`DELETE /profile/me/`**

**Заголовок:** `Authorization: Bearer <access-токен>`

**Ответ (200):**
```json
{
  "detail": "Аккаунт успешно удален."
}
```

> Флаги `is_active` и `is_agreed_to_terms` переводятся в `False`, связанные проекты переводятся в архив. 
При повторной регистрации с тем же email аккаунт восстанавливается.

### 3. Сменить email

**`POST /profile/email-change/`**

**Заголовок:** `Authorization: Bearer <access-токен>`

```json
{
  "new_email": "newemail@example.com"
}
```
> **Важно:** При смене email его подтверждение обязательно. Письмо приходит в консоль Django (на dev-сервере `EMAIL_BACKEND=console`). Ссылка для подтверждения имеет формат: `{HOST_URL}/{key}`.

**Ответ (200):**
```json
{
  "detail": "Ссылка подтверждения отправлена на новый email."
}
```

### 4. Загрузить/удалить аватар

**`POST /profile/me/avatar/`** — загрузить (multipart/form-data)
**`DELETE /profile/me/avatar/`** — удалить

**Заголовок:** `Authorization: Bearer <access-токен>`

**POST (multipart/form-data):**
```
file: <файл изображения jpeg/jpg/png до 10MB>
```

**Ответ (201):**
```json
{
  "avatar_url": "https://minio.example.com/avatars/uuid.jpg"
}
```

### 5. Опыт работы

**`POST /profile/me/experience/`** — создать
**`PUT /profile/me/experience/{exp_id}/`** — обновить
**`DELETE /profile/me/experience/{exp_id}/`** — удалить

**Заголовок:** `Authorization: Bearer <access-токен>`

```json
{
  "company": "ООО Ромашка",
  "position": "Senior Developer",
  "responsibilities": "Разработка и ревью кода",
  "start_date": "2023-01-01",
  "end_date": "2024-06-01"
}
```

> `end_date` опционален (если не указан — текущее место работы). GET-метод не поддерживается (только POST, PUT, DELETE).

### 6. Посмотреть чужой профиль

**`GET /profile/{user_id}/`**

**Заголовок:** `Authorization: Bearer <access-токен>`

### 7. Список пользователей

**`GET /profile/`**

**Заголовок:** `Authorization: Bearer <access-токен>`

**Параметры:**
- `spec_id` — ID специализаций через запятую
- `skill_id` — ID навыков через запятую
- `search` — поиск по имени, фамилии, стране, городу
- `sort_by` — `newest` (по умолчанию) или `relevance` (только с search)

---

## Формат авторизации

Все защищённые ручки требуют заголовок:

```
Authorization: Bearer <access-токен>
```

Токен также автоматически устанавливается в cookie `access-token` (не HttpOnly, доступен из JS), что позволяет работать через браузер.

---


[⬅ Назад на главную](../README.md)