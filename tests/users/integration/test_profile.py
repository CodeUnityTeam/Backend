from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.conftest import (
    SkillFactory,
    SpecializationFactory,
    WorkFormatFactory,
)

User = get_user_model()
PROFILE_ME_URL = reverse('users:my-profile')


def test_get_my_profile_successful(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Успешный GET-запрос профиля авторизованного пользователя.

    Проверяет статус ответа 200 OK и точное соответствие полей
    ответа данным созданной фикстуры пользователя.
    """
    api_client.force_authenticate(user=verified_user)

    response: Any = api_client.get(PROFILE_ME_URL)

    assert response.status_code == status.HTTP_200_OK

    # Проверяем базовое соответствие полей фикстуры и ответа API
    assert response.data['email'] == getattr(verified_user, 'email')
    assert response.data['first_name'] == getattr(verified_user, 'first_name')
    assert response.data['last_name'] == getattr(verified_user, 'last_name')
    assert response.data['onboarding_completed'] is False


@pytest.mark.django_db
def test_patch_my_profile_completes_onboarding(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Успешный PATCH-запрос на изменение текстовых полей профиля.

    Проверяет сохранение данных в базу и автоматическое переключение
    флага onboarding_completed в True.
    """
    api_client.force_authenticate(user=verified_user)

    payload: dict[str, str] = {
        'first_name': 'Алексей',
        'last_name': 'Петров',
        'city': 'Москва',
    }

    response: Any = api_client.patch(PROFILE_ME_URL, data=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.data['first_name'] == 'Алексей'
    assert response.data['last_name'] == 'Петров'
    assert response.data['onboarding_completed'] is True

    # Проверяем, что изменения зафиксированы в самой СУБД
    verified_user.refresh_from_db()
    assert getattr(verified_user, 'first_name') == 'Алексей'
    assert getattr(verified_user, 'last_name') == 'Петров'
    assert getattr(verified_user, 'onboarding_completed') is True


@pytest.mark.django_db
def test_patch_my_profile_updates_m2m_relations(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Успешное обновление M2M связей (навыки, специализации, форматы).

    Проверяет, что списки ID корректно привязываются к пользователю,
    а ответ возвращает развернутые сериализованные объекты.
    """
    api_client.force_authenticate(user=verified_user)

    # Генерируем тестовые объекты для связей M2M
    skill_1: Model = SkillFactory()
    skill_2: Model = SkillFactory()
    spec: Model = SpecializationFactory()
    w_format: Model = WorkFormatFactory()

    payload: dict[str, Any] = {
        'skills': [str(skill_1.pk), str(skill_2.pk)],
        'specializations': [str(spec.pk)],
        'workformats': [str(w_format.pk)],
    }

    response: Any = api_client.patch(PROFILE_ME_URL, data=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.data['onboarding_completed'] is True

    # Так как MeProfileRetrieveSerializer разворачивает объекты,
    # проверяем длину списков в ответе
    assert len(response.data['skills']) == 2
    assert len(response.data['specializations']) == 1
    assert len(response.data['workformats']) == 1

    # Проверяем физическое наличие связей в СУБД у инстанса пользователя
    assert getattr(verified_user, 'skills').count() == 2
    assert getattr(verified_user, 'specializations').count() == 1
    assert getattr(verified_user, 'workformats').count() == 1
