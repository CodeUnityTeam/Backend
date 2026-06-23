from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from projects.models import Project, WorkFormat
from users.models import Skill, Specialization

User = get_user_model()


@pytest.fixture
def employer() -> User:
    """Пользователь с ролью 'employer' (наниматель)."""
    return User.objects.create_user(
        email='employer@test.com',
        password='user887089',
        first_name='Иван',
        last_name='Иванов',
        projects_relation=User.ProjectsRelationChoices.EMPLOYER,
    )


@pytest.fixture
def worker() -> User:
    """Пользователь с ролью 'worker' (исполнитель)."""
    return User.objects.create_user(
        email='worker@test.com',
        password='user887089',
        first_name='Петр',
        last_name='Петров',
        projects_relation=User.ProjectsRelationChoices.WORKER,
    )


@pytest.fixture
def anonymous() -> None:
    """Анонимный пользователь (неавторизованный)."""
    return


@pytest.fixture
def api_client() -> APIClient:
    """Апи-клиент для тестов (аналог requests)."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def anonymous_api_client(api_client: APIClient) -> APIClient:
    """Анонимный API-клиент (без авторизации)."""
    return api_client


@pytest.fixture
def employer_api_client(api_client: APIClient, employer: User) -> APIClient:
    """API-клиент авторизованного нанимателя."""
    api_client.force_authenticate(user=employer)
    return api_client


@pytest.fixture
def worker_api_client(api_client: APIClient, worker: User) -> APIClient:
    """API-клиент авторизованного работника."""
    api_client.force_authenticate(user=worker)
    return api_client


@pytest.fixture
def project(employer):
    """Создаёт проект с реальным UUID и корректными M2M-связями."""
    start_date_obj = date.today()
    end_date_obj = start_date_obj + timedelta(days=90)
    start_date = start_date_obj.isoformat()
    end_date = end_date_obj.isoformat()
    proj = Project.objects.create(
        title='Test Project',
        short_desc='Short description',
        location='Moscow',
        status_project='published',
        author=employer,
        start_date=start_date,
        end_date=end_date,
    )
    skill_ids = [
        '0adaba4a-e582-4e30-af84-5ecf7957f595',
        '0b96fe31-f8c2-4750-ad92-946ce0ea71f0',
    ]
    spec_ids = [
        'eb943c2d-0859-4363-8884-c51d42b4a587',
        'ebf19476-218f-491b-bd3b-b8cc8877321d',
    ]
    format_ids = [
        '450eab94-627f-4805-81b0-e8bcca4a0e7c',
    ]
    skills = Skill.objects.filter(skill_id__in=skill_ids)
    specs = Specialization.objects.filter(spec_id__in=spec_ids)
    formats = WorkFormat.objects.filter(format_id__in=format_ids)
    proj.skills.set(skills)
    proj.specializations.set(specs)
    proj.project_format.set(formats)
    return proj


@pytest.fixture
def project_id(project: Project) -> str:
    """Возвращает ID проекта."""
    return str(project.project_id)


@pytest.fixture
def user_id_worker(worker: User) -> str:
    """Возвращает ID пользователя worker'a."""
    return str(worker.user_id)


@pytest.fixture
def user_id_employer(employer: User) -> str:
    """Возвращает ID пользователя employer'a."""
    return str(employer.user_id)


@pytest.fixture
def user_id(project) -> str:
    """Возвращает ID пользователя, создающего проект (автора)."""
    return str(project.author.user_id)
