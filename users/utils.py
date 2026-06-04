import os


def get_frontend_url(action_type: str, key: str) -> str:
    """Генерирует ссылку на фронтенд для различных типов операций."""
    frontend_url: str = os.getenv("HOST_URL", "http://localhost:3000")

    if action_type == "email":
        return f"{frontend_url}/{key}"

    if action_type == "password":
        return f"{frontend_url}/password-reset/confirm/{key}"

    raise ValueError(f"Неизвестный тип операции: {action_type}")
