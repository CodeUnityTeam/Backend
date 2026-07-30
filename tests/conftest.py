import datetime
import uuid
from typing import Any, Generator, Type

import factory
import pytest
from allauth.account.models import EmailAddress
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db.models import Model
from django.utils import timezone
from factory.django import DjangoModelFactory
from pytest_mock import MockerFixture
from rest_framework.test import APIClient

from config.settings_test import postgres_container, redis_container
from projects.models import Project, WorkFormat
from projects.models import Response as ProjectResponse
from users.models import Skill, Specialization, User, UserLike

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


class SkillFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации навыков."""

    class Meta:
        model = Skill

    name = factory.Sequence(lambda n: f'Skill_{n}')


class SpecializationFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации специализаций."""

    class Meta:
        model = Specialization

    name = factory.Sequence(lambda n: f'Specialization_{n}')


class WorkFormatFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации форматов работы."""

    class Meta:
        model = WorkFormat

    name = factory.Sequence(lambda n: f'Format_{n}')


class EmployerFactory(UserFactory):
    """Фабрика для генерации пользователей с ролью Наниматель."""

    projects_relation = User.ProjectsRelationChoices.EMPLOYER


class UserLikeFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации лайков между нанимателем и соискателем."""

    class Meta:
        model = UserLike

    employer = factory.SubFactory(EmployerFactory)
    worker = factory.SubFactory(UserFactory)


class ProjectFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации проектов."""

    class Meta:
        model = Project

    title = factory.Sequence(lambda n: f'Project_{n}')
    author = factory.SubFactory(EmployerFactory)
    start_date = factory.LazyAttribute(lambda _: timezone.now().date())
    end_date = factory.LazyAttribute(
        lambda o: o.start_date + datetime.timedelta(days=30),
    )


class ProjectResponseFactory(factory.django.DjangoModelFactory):
    """Фабрика для генерации откликов соискателей на проекты."""

    class Meta:
        model = ProjectResponse

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(UserFactory)
    initiator_type = 'applicant'
    status_resp = 'pending'


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
    """Mock-фикстура для изоляции асинхронной отправки писем через Celery."""
    from core import tasks
    return mocker.patch.object(tasks.send_async_template_email, 'delay')


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


@pytest.fixture
def employer_user() -> Model:
    """Фикстура авторизованного нанимателя."""
    return EmployerFactory()


# =============================================================================
# ГЛОБАЛЬНЫЕ АВТО-ФИКСТУРЫ ОЧИСТКИ
# =============================================================================

@pytest.fixture(autouse=True)
def _clear_cache_before_each_test() -> None:
    """Гарантированно очищает кэш Redis перед запуском каждого теста."""
    cache.clear()
