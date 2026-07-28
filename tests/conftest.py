import uuid
from typing import Any, Generator, Type

import factory
import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db.models import Model
from factory.django import DjangoModelFactory
from pytest_mock import MockerFixture
from rest_framework.test import APIClient

from config.settings_test import postgres_container, redis_container
from users.utils import email_service as real_email_service

User: Type[Model] = get_user_model()


# =============================================================================
# ОСТАНОВКА ТЕСТОВОГО КОНТЕЙНЕРА
# =============================================================================

def pytest_unconfigure(config: Any) -> None:
    """Гарантированно удаляет Docker-контейнеры после завершения тестов."""
    postgres_container.stop()
    redis_container.stop()


# =============================================================================
# ФАБРИКИ (FACTORY BOY)
# =============================================================================

class UserFactory(DjangoModelFactory):
    """Фабрика для кастомной модели User."""

    class Meta:
        model = User
        django_get_or_create = ('email',)

    user_id: uuid.UUID = factory.LazyFunction(uuid.uuid4)
    email: str = factory.Sequence(lambda n: f'user_{n}@example.com')
    first_name: str = factory.Faker('first_name')
    last_name: str = factory.Faker('last_name')
    is_active: bool = True
    role: str = 'user'
    projects_relation: str = 'worker'

    @classmethod
    def _create(
        cls, model_class: Type[Model], *args: Any, **kwargs: Any,
    ) -> Model:
        """Переопределяем создание для корректного хеширования пароля."""
        password: str = kwargs.pop('password', 'secret_password_123')
        user: Any = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user


class EmailAddressFactory(DjangoModelFactory):
    """Фабрика для записей EmailAddress из django-allauth."""

    class Meta:
        model = EmailAddress

    user: factory.SubFactory = factory.SubFactory(UserFactory)
    email: factory.SelfAttribute = factory.SelfAttribute('user.email')
    verified: bool = False
    primary: bool = True


# =============================================================================
# ГЛОБАЛЬНЫЕ ФИКСТУРЫ PYTEST
# =============================================================================

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(
    db: Any,
) -> Generator[None, None, None]:
    """Автоматически разрешает всем тестам работать с базой данных."""
    yield


@pytest.fixture(autouse=True)
def setup_current_site() -> Site:
    """Гарантирует наличие Site в базе данных для корректной работы allauth."""
    site, _ = Site.objects.get_or_create(
        id=1,
        defaults={'domain': 'localhost:8000', 'name': 'Test Site'},
    )
    return site


@pytest.fixture
def api_client() -> APIClient:
    """Фикстура REST Framework клиента для интеграционных тестов."""
    return APIClient()


@pytest.fixture
def mock_email_service(mocker: MockerFixture) -> Any:
    """Mock-фикстура для изоляции отправки писем через EmailService."""
    return mocker.patch.object(real_email_service, 'send_template_email')


@pytest.fixture
def verified_user() -> Model:
    """Создает активного пользователя с подтвержденным email."""
    user: Model = UserFactory(email='verified@example.com')
    EmailAddressFactory(user=user, verified=True)
    return user


@pytest.fixture
def unverified_user() -> Model:
    """Создает активного пользователя с НЕподтвержденным email."""
    user: Model = UserFactory(email='unverified@example.com')
    EmailAddressFactory(user=user, verified=False)
    return user
