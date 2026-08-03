from typing import Any

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.constants.feedback import FEEDBACK_STATUS_CLOSED
from core.constants.projects import ARCHIVED
from tests.conftest import (
    EmployerFactory,
    FeedbackFormFactory,
    ProjectFactory,
    ProjectParticipantFactory,
    ProjectResponseFactory,
)

User = get_user_model()
MY_PROFILE_URL = reverse('users:my-profile')


def test_deactivate_worker_account_successful(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Успешное мягкое удаление аккаунта пользователя с ролью WORKER.

    Проверяет закрытие форм обратной связи, удаление участий и откликов,
    а также сброс флагов активности и верификации email.
    """
    api_client.force_authenticate(user=verified_user)

    # Готовим шлейф связанных данных для соискателя (WORKER)
    FeedbackFormFactory(user=verified_user)
    ProjectParticipantFactory(user=verified_user)
    ProjectResponseFactory(user=verified_user)

    # Гарантируем, что запись верификации почты изначально активна
    EmailAddress.objects.filter(
        user=verified_user, email__iexact=getattr(verified_user, 'email'),
    ).update(verified=True)

    # Выполняем DELETE запрос
    response: Any = api_client.delete(MY_PROFILE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'detail': 'Аккаунт успешно удален.'}

    # Проверяем каскадные изменения в СУБД
    verified_user.refresh_from_db()
    assert getattr(verified_user, 'is_active') is False
    assert getattr(verified_user, 'is_agreed_to_terms') is False

    # Проверяем сброс верификации почты
    email_entry = EmailAddress.objects.filter(
        user=verified_user, email__iexact=getattr(verified_user, 'email'),
    ).first()
    assert email_entry is not None
    assert email_entry.verified is False

    # Проверяем закрытие фидбек-форм по ОФИЦИАЛЬНОЙ константе
    assert (
        getattr(verified_user, 'feedback_forms')
        .filter(status=FEEDBACK_STATUS_CLOSED)
        .count() == 1
    )
    assert getattr(verified_user, 'project_participations').count() == 0
    assert getattr(verified_user, 'responses').count() == 0


def test_deactivate_employer_account_successful(
    api_client: APIClient,
) -> None:
    """Успешное мягкое удаление аккаунта пользователя с ролью EMPLOYER.

    Дополнительно проверяет автоматический перевод всех созданных
    нанимателем проектов в архивный статус ARCHIVED.
    """
    # Создаем и верифицируем нанимателя
    employer = EmployerFactory()
    api_client.force_authenticate(user=employer)

    # Конструируем запись EmailAddress
    EmailAddress.objects.create(
        user=employer,
        email=getattr(employer, 'email'),
        primary=True,
        verified=True,
    )

    # Готовим связанные данные, включая собственные проекты нанимателя
    FeedbackFormFactory(user=employer)
    ProjectFactory(author=employer, status_project='draft')

    # Выполняем DELETE запрос
    response: Any = api_client.delete(MY_PROFILE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'detail': 'Аккаунт успешно удален.'}

    # Проверяем каскадные изменения нанимателя в СУБД
    employer.refresh_from_db()
    assert getattr(employer, 'is_active') is False

    email_entry = EmailAddress.objects.filter(
        user=employer, email__iexact=getattr(employer, 'email'),
    ).first()
    assert email_entry.verified is False

    # Проверяем, что проект нанимателя перешел в статус ARCHIVED по константе
    assert (
        getattr(employer, 'projects')
        .filter(status_project=ARCHIVED)
        .count() == 1
    )
    assert (
        getattr(employer, 'feedback_forms')
        .filter(status=FEEDBACK_STATUS_CLOSED)
        .count() == 1
    )
