from typing import Any

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.constants.users import MSG_RESENT
from tests.conftest import UserFactory

User = get_user_model()


def test_successful_registration(
    api_client: APIClient, mock_email_service: Any,
) -> None:
    """Успешная первичная регистрация нового пользователя.

    Проверяет создание аккаунта с неподтвержденной почтой,
    отправку первичного письма и соответствие ответа стандартной строке.
    """
    url: str = reverse('users:rest_register')
    payload: dict[str, str] = {
        'email': 'new_user@example.com',
        'password': 'StrongPassword123!',
        'first_name': 'Иван',
        'last_name': 'Иванов',
    }

    response: Any = api_client.post(url, data=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data == {'detail': 'Письмо с подтверждением выслано.'}

    user: Model | None = User.objects.filter(
        email='new_user@example.com',
    ).first()
    assert user is not None
    assert getattr(user, 'first_name') == 'Иван'
    assert getattr(user, 'last_name') == 'Иванов'
    assert getattr(user, 'is_active') is True

    email_address: EmailAddress | None = EmailAddress.objects.filter(
        user=user,
    ).first()
    assert email_address is not None
    assert email_address.verified is False

    mock_email_service.assert_called_once()


def test_registration_fails_if_email_exists_and_verified(
    api_client: APIClient, verified_user: Model, mock_email_service: Any,
) -> None:
    """Запрет повторной регистрации на подтвержденный email.

    Должен вызывать ошибку валидации поля email.
    """
    url: str = reverse('users:rest_register')
    payload: dict[str, str] = {
        'email': getattr(verified_user, 'email'),
        'password': 'AnotherPassword123!',
        'first_name': 'Петр',
        'last_name': 'Петров',
    }

    response: Any = api_client.post(url, data=payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.data
    assert (
        'Пользователь с таким email уже зарегистрирован.'
        in response.data['email']
    )

    mock_email_service.assert_not_called()


def test_registration_resends_email_if_not_verified(
    api_client: APIClient, mock_email_service: Any,
) -> None:
    """Повторная регистрация активного аккаунта с неподтвержденной почтой.

    Пользователь существует и активен, но его почта еще не верифицирована.
    Сериализатор должен пропустить валидацию email, зайти в метод save()
    и выдать 201 Created вместе с MSG_RESENT через кастомное исключение.
    """
    test_email: str = 'retry_unverified@example.com'

    # Создаем активного пользователя
    existing_user: Model = UserFactory(email=test_email, is_active=True)

    # Гарантируем, что запись EmailAddress существует и verified=False
    EmailAddress.objects.update_or_create(
        user=existing_user,
        email=test_email,
        defaults={'verified': False, 'primary': True},
    )

    url: str = reverse('users:rest_register')
    payload: dict[str, str] = {
        'email': test_email,
        'password': 'Password123!',
        'first_name': 'Иван',
        'last_name': 'Иванов',
    }

    response: Any = api_client.post(url, data=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data == {'detail': MSG_RESENT}


def test_registration_reactivates_soft_deleted_user(
    api_client: APIClient, mock_email_service: Any,
) -> None:
    """Реактивация мягко удаленного (is_active=False) пользователя.

    Пользователь был временно деактивирован. При повторной регистрации
    аккаунт должен снова стать активным (is_active=True), а API выдает
    201 и MSG_RESENT через ImmediateResponseException.
    """
    test_email: str = 'retry_inactive@example.com'

    # Создаем мягко удаленного пользователя
    inactive_user: Model = UserFactory(email=test_email, is_active=False)

    # Гарантируем, что запись EmailAddress для него существует и verified=False
    EmailAddress.objects.update_or_create(
        user=inactive_user,
        email=test_email,
        defaults={'verified': False, 'primary': True},
    )

    url: str = reverse('users:rest_register')
    payload: dict[str, str] = {
        'email': test_email,
        'password': 'NewPassword123!',
        'first_name': 'Реактивированный',
        'last_name': 'Пользователь',
    }

    response: Any = api_client.post(url, data=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data == {'detail': MSG_RESENT}

    # Жестко проверяем, что в БД флаг изменился на True
    inactive_user.refresh_from_db()
    assert getattr(inactive_user, 'is_active') is True
