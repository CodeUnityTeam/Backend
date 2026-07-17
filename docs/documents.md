# Документы

Раздел, предназначенный для юридических документов: правил площадки, согласия на обработку персональных данных, политики конфиденциальности.

**URL:** `/api/v1/documents/`

**Методы:**

- `GET` - получить список документов

**Формат ответа**

```json
[
    {
        "slug": "privacy_policy",
        "title": "Политика конфиденциальности",
        "file_url": "https://example.com/static/documents/Code_Unity_privacy_policy.pdf"
    },
    {
        "slug": "platform_rules",
        "title": "Правила пользования платформой",
        "file_url": "https://example.com/static/documents/Code_Unity_platform_rules.pdf"
    },
    {
        "slug": "personal_data_processing",
        "title": "Обработка персональных данных",
        "file_url": "https://example.com/static/documents/Code_Unity_personal_data_processing.pdf"
    }
]
```


## Как добавить новый документ

1. Положить PDF-файл в `documents/static/documents/`
2. Добавить запись в словарь `DOCUMENTS` в [`documents/views.py`](../documents/views.py)
3. Деплой — `collectstatic` скопирует файл в общую статику
