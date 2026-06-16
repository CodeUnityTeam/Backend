# API авторизации и пользователей

**Базовый URL:** `https://dev.code-unity.ru/api/v1/user/`

**Префикс:** `/api/v1/user/`

Сервис создания учетных записей и авторизации пользователей.

### Возможности
- Регистрация
- Стандартная авторизация
- Регистрация и авторизация через социальные аккаунты
- Изменения учетных данных (email, пароль)
- Работа с WJT токенами

---

## 1. Регистрация (email + пароль)

### 1.1. Создать аккаунт

**`POST /auth/registration/`**

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "first_name": "Иван",
  "last_name": "Петров"
}
```
Все поля обязательные!

**Ответ (201):**
```json
{
  "detail": "Письмо с подтверждением успешно отправлено на ваш email."
}
```

> **Важно:** `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` — подтверждение email обязательно. Письмо приходит в консоль Django (на dev-сервере `EMAIL_BACKEND=console`). Ссылка для подтверждения имеет формат: `{HOST_URL}/{key}`.

### 1.2. Подтвердить email

Перейти по ссылке из письма (GET-запрос на фронтенд, который затем запрашивает бэкенд для подтверждения). Ручка подтверждения — стандартная `dj_rest_auth`: **`POST /auth/registration/verify-email/`** с ключом.

**Ответ (201):**
```json
{
  "key": "sarjtsrtjsthasetrhserthaaAHarhaZzrGHA"
}
```

---

## 2. Вход (login)

### 2.1. Логин по email и паролю

**`POST /auth/login/`**

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

**Ответ (200):**
```json
{
  "access": "eyJhbGciOiJIUzI1Ni...",
  "refresh": "eyJhbGciOiJIUzI1Ni...",
  "access_expiration": "2026-06-18T09:00:00Z",
  "refresh_expiration": "2026-06-18T09:00:00Z",
  "user": {
    "pk": "uuid-пользователя",
    "email": "user@example.com",
    ...
  }
}
```

> **Важно:** `access` и `refresh` — это JWT-токены. `access` живёт 15 минут, `refresh` — 3 дня (настройка `SIMPLE_JWT`). Токены также устанавливаются в cookies: `access-token` и `refresh-token`.

---

## 3. Социальная авторизация (OAuth2)

### 3.1. Получить URL для редиректа на провайдера

**`GET /auth/google/url/`**
**`GET /auth/yandex/url/`**
**`GET /auth/mailru/url/`**

**Ответ (200):**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=..."
}
```

Фронтенд редиректит пользователя на этот URL. Пользователь авторизуется у провайдера, и провайдер редиректит обратно на `redirect_uri` (callback URL) с параметром `?code=...`.

### 3.2. Обменять code на JWT

**`POST /auth/google/`**
**`POST /auth/yandex/`**
**`POST /auth/mailru/`**

```json
{
  "code": "код_авторизации_от_провайдера"
}
```

**Ответ (200):** Аналогичен ответу логина — `access`, `refresh`, `user`.

> **Важно:** Поле `code` автоматически декодируется из URL-encoding на бэкенде. При певрчном входе через провайдера автоматически создается пользователь, поля заполняются на основе данных, полученных от провайдера, подтверждения email не требуется.

---

## 4. Работа с токенами

### 4.1. Обновить access-токен

**`POST /auth/token/refresh/`**

```json
{
  "refresh": "eyJhbGciOiJIUzI1Ni... (refresh-токен)"
}
```

**Ответ (200):**
```json
{
  "access": "новый access-токен",
  "refresh": "новый refresh-токен",
  "access_expiration": "...",
  "refresh_expiration": "..."
}
```

> `ROTATE_REFRESH_TOKENS = True` — при каждом обновлении выдаётся новая пара токенов, старый refresh-токен чернится.

### 4.2. Проверить токен

**`POST /auth/token/verify/`**

```json
{
  "token": "eyJhbGciOiJIUzI1Ni... (access-токен)"
}
```

**Ответ (200):** пустое тело `{}` — токен валиден.

### 4.3. Выйти (logout)

**`POST /auth/logout/`**

```json
{
  "refresh": "eyJhbGciOiJIUzI1Ni... (refresh-токен)"
}
```

**Заголовок:** `Authorization: Bearer <access-токен>`

**Ответ (200):**
```json
{
  "detail": "Выход из системы выполнен."
}
```

---

## 5. Сброс и смена пароля

### 5.1. Запросить сброс пароля

**`POST /auth/password/reset/`**

```json
{
  "email": "user@example.com"
}
```

**Ответ (200):**
```json
{
  "detail": "Письмо с инструкциями по восстановлению пароля выслано."
}
```

Ссылка в письме: `{HOST_URL}/password-reset/confirm/{temp_key}`

### 5.2. Подтвердить сброс пароля

**`POST /auth/password/reset/confirm/`**

```json
{
  "uid": "...",
  "token": "...",
  "new_password1": "NewPass123!",
  "new_password2": "NewPass123!"
}
```

### 5.3. Сменить пароль (будучи авторизованным)

**`POST /auth/password/change/`**

**Заголовок:** `Authorization: Bearer <access-токен>`

```json
{
  "new_password": "новый_пароль"
}
```

**Ответ (200):**
```json
{
  "detail": "Новый пароль сохранён."
}
```

> **Важно:** Кастомный сериализатор принимает одно поле `new_password` (без `new_password1`/`new_password2`).
---

## 6. Последовательность действий (сценарии)

### Сценарий A: Регистрация через email

```
1. POST /auth/registration/
   → { email, password, first_name, last_name }
   ← 201 { detail: "Письмо отправлено" }

2. Пользователь переходит по ссылке из письма
   → POST /auth/registration/verify-email/ (с ключом)
   ← 200 { detail: "Email подтверждён" }

3. POST /auth/login/
   → { email, password }
   ← 200 { access, refresh, user }

4. GET /profile/me/
   → Authorization: Bearer <access>
   ← 200 { ... данные профиля ... }

5. PATCH /profile/me/
   → Authorization: Bearer <access>
   → { city, about_me, skills, specializations, workformats }
   ← 200 { ... обновлённый профиль ... }
```

### Сценарий B: Вход через Google

```
1. GET /auth/google/url/
   ← 200 { authorization_url: "https://accounts.google.com/..." }

2. Редирект пользователя на authorization_url
   → Пользователь авторизуется в Google
   → Google редиректит на callback_url?code=XXXXX

3. POST /auth/google/
   → { code: "XXXXX" }
   ← 200 { access, refresh, user }
```

### Сценарий C: Работа с токенами

```
1. POST /auth/login/
   ← 200 { access, refresh, ... }

2. GET /profile/me/
   → Authorization: Bearer <access>
   ← 200 { ... }

3. POST /auth/token/refresh/
   → { refresh: "<refresh-токен>" }
   ← 200 { access: "новый", refresh: "новый" }

4. POST /auth/logout/
   → Authorization: Bearer <access>
   → { refresh: "<refresh-токен>" }
   ← 200 { detail: "Выход выполнен" }
```

### Сценарий D: Сброс пароля

```
1. POST /auth/password/reset/
   → { email: "user@example.com" }
   ← 200 { detail: "Письмо выслано" }

2. Пользователь переходит по ссылке из письма
   → POST /auth/password/reset/confirm/
   → { uid, token, new_password1, new_password2 }
   ← 200 { detail: "Пароль изменён" }

3. POST /auth/login/ с новым паролем
```

---

## 7. Формат авторизации

Все защищённые ручки требуют заголовок:

```
Authorization: Bearer <access-токен>
```

Токен также автоматически устанавливается в cookie `access-token` (не HttpOnly, доступен из JS), что позволяет работать через браузер.

---

[⬅ Назад на главную](../README.md)