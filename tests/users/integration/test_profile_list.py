from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.conftest import (
    EmployerFactory,
    ProjectFactory,
    ProjectResponseFactory,
    SkillFactory,
    UserFactory,
    UserLikeFactory,
)

User = get_user_model()
PROFILE_LIST_URL = reverse('users:profile-list')


def test_profile_list_access_denied_for_worker(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Проверка прав доступа к эндпоинту списков соискателей.

    Пользователь с ролью WORKER должен гарантированно получить
    ответ 403 Forbidden согласно IsEmployer пермишену.
    """
    api_client.force_authenticate(user=verified_user)

    response: Any = api_client.get(PROFILE_LIST_URL)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_profile_list_text_search_by_fields(
    api_client: APIClient, employer_user: Model,
) -> None:
    """Успешный поиск соискателей по текстовой подстроке.

    Проверяет частичное совпадение по имени, фамилии, стране и городу.
    """
    api_client.force_authenticate(user=employer_user)

    # Создаем тестовую выборку соискателей
    UserFactory(first_name='Иван', last_name='Иванов', city='Москва')
    UserFactory(first_name='Джон', last_name='Смит', city='Лондон')
    UserFactory(first_name='Петр', last_name='Петров', country='Беларусь')

    # Тестируем поиск по городу
    response_1: Any = api_client.get(f'{PROFILE_LIST_URL}?search=Москва')
    assert response_1.status_code == status.HTTP_200_OK
    assert response_1.data['total'] == 1
    assert response_1.data['items'][0]['first_name'] == 'Иван'

    # Тестируем поиск по имени
    response_2: Any = api_client.get(f'{PROFILE_LIST_URL}?search=Петр')
    assert response_2.status_code == status.HTTP_200_OK
    assert response_2.data['total'] == 1
    assert response_2.data['items'][0]['last_name'] == 'Петров'


def test_profile_list_filtering_by_m2m_skills(
    api_client: APIClient, employer_user: Model,
) -> None:
    """Успешная фильтрация соискателей по списку UUID навыков через запятую.

    Проверяет, что подзапросы relevance отсекают пользователей без совпадений.
    """
    api_client.force_authenticate(user=employer_user)

    skill_python: Model = SkillFactory(name='Python')
    skill_js: Model = SkillFactory(name='JavaScript')

    user_1: Model = UserFactory(first_name='Питонист')
    getattr(user_1, 'skills').add(skill_python)

    user_2: Model = UserFactory(first_name='Фронтендер')
    getattr(user_2, 'skills').add(skill_js)

    # Запрашиваем только тех, у кого есть навык Python
    response: Any = api_client.get(
        f'{PROFILE_LIST_URL}?skill_ids={skill_python.pk}',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total'] == 1
    assert response.data['items'][0]['first_name'] == 'Питонист'


def test_profile_list_sorting_by_popularity(
    api_client: APIClient, employer_user: Model,
) -> None:
    """Успешная сортировка выдачи по количеству лайков соискателей.

    Проверяет, что соискатель с большим числом лайков идет в начале списка.
    """
    api_client.force_authenticate(user=employer_user)

    # Создаем дополнительного нанимателя для накрутки лайков
    another_employer: Model = EmployerFactory()

    worker_popular: Model = UserFactory(first_name='Популярный')
    UserFactory(first_name='Обычный')

    # Накручиваем 2 лайка для первого соискателя от разных нанимателей
    UserLikeFactory(employer=employer_user, worker=worker_popular)
    UserLikeFactory(employer=another_employer, worker=worker_popular)

    # Делаем запрос с сортировкой по популярности
    response: Any = api_client.get(f'{PROFILE_LIST_URL}?sort_by=popularity')

    assert response.status_code == status.HTTP_200_OK
    # Первым в списке результатов должен идти соискатель с лайками
    assert response.data['items'][0]['first_name'] == 'Популярный'


def test_profile_list_scenario_responses(
    api_client: APIClient, employer_user: Model,
) -> None:
    """Успешное переключение списков в режим просмотра откликов соискателей.

    Проверяет отдачу структуры карточек через UserResponseCardSerializer.
    """
    api_client.force_authenticate(user=employer_user)

    # Создаем проект текущего нанимателя и отклик на него
    my_project: Model = ProjectFactory(
        title='Тестовый проект', author=employer_user,
    )
    applicant: Model = UserFactory(first_name='Соискатель')
    ProjectResponseFactory(project=my_project, user=applicant)

    response: Any = api_client.get(f'{PROFILE_LIST_URL}?responses=true')

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total'] == 1
    # Проверяем специфичные для UserResponseCardSerializer поля карточки
    assert response.data['items'][0]['project_title'] == 'Тестовый проект'
    assert (
        response.data['items'][0]['profile']['first_name'] == 'Соискатель'
    )


def test_profile_list_mutually_exclusive_params_returns_empty(
    api_client: APIClient, employer_user: Model,
) -> None:
    """Запрет одновременного запроса откликов и избранного соискателей.

    При передаче обоих параметров бизнес-логика должна вернуть пустой QuerySet.
    """
    api_client.force_authenticate(user=employer_user)

    response: Any = api_client.get(
        f'{PROFILE_LIST_URL}?responses=true&favourites=true',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total'] == 0
    assert len(response.data['items']) == 0
