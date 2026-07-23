from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


def test_login_successful_sets_cookies(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Успешный вход пользователя с подтвержденным email.

    Проверяет, что при валидных данных система возвращает 200 OK
    и устанавливает JWT-токены в куки (access-token и refresh-token).
    """
    url: str = reverse('users:rest_login')
    payload: dict[str, str] = {
        'email': getattr(verified_user, 'email'),
        'password': 'secret_password_123',  # Дефолтный пароль нашей фабрики
    }

    response: Any = api_client.post(url, data=payload)

    assert response.status_code == status.HTTP_200_OK

    # Проверяем, что в заголовках ответа выставились куки для JWT
    cookies: Any = response.cookies
    assert 'access-token' in cookies
    assert 'refresh-token' in cookies


def test_login_fails_if_email_not_verified(
    api_client: APIClient, unverified_user: Model,
) -> None:
    """Блокировка входа, если email пользователя не подтвержден.

    Так как в настройках ACCOUNT_EMAIL_VERIFICATION = 'mandatory',
    dj-rest-auth должен отклонить запрос с ошибкой 400 Bad Request.
    """
    url: str = reverse('users:rest_login')
    payload: dict[str, str] = {
        'email': getattr(unverified_user, 'email'),
        'password': 'secret_password_123',
    }

    response: Any = api_client.post(url, data=payload)

    # allauth блокирует вход неподтвержденных пользователей
    assert response.status_code == status.HTTP_400_BAD_REQUEST
