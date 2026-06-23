import pytest
from django.urls import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

ANONYMOUS_CLIENT = 'anonymous_api_client'
EMPLOYER_CLIENT = 'employer_api_client'
WORKER_CLIENT = 'worker_api_client'

LIST_PROJECTS = 'project-list'
DETAIL_PROJECT = 'project-detail'
LIKE_PROJECT = 'project-like'
RECOMMEND_PROJECT = 'project-recommendations'
INVITE_TO_PROJECT = 'project-invite'
CREATE_RESPONSE = 'project-responses-create'
POST = 'post'
GET = 'get'
PATCH = 'patch'
DELETE = 'delete'
from typing import Optional


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_fixture, url_name, method, url_kwargs, payload, expected_status',
    [
        # Public GET: список проектов (не требует проекта) ---
        (ANONYMOUS_CLIENT, LIST_PROJECTS, GET, {}, None, HTTP_200_OK),
        (EMPLOYER_CLIENT, LIST_PROJECTS, GET, {}, None, HTTP_200_OK),
        (WORKER_CLIENT, LIST_PROJECTS, GET, {}, None, HTTP_200_OK),
        # Recommendations (не требует конкретного проекта) ---
        (
            ANONYMOUS_CLIENT,
            RECOMMEND_PROJECT,
            GET,
            {},
            None,
            HTTP_401_UNAUTHORIZED,
        ),
        (EMPLOYER_CLIENT, RECOMMEND_PROJECT, GET, {}, None, HTTP_200_OK),
        (WORKER_CLIENT, RECOMMEND_PROJECT, GET, {}, None, HTTP_200_OK),
        # Detail: доступ к существующему проекту (проверяем права) ---
        (
            ANONYMOUS_CLIENT,
            DETAIL_PROJECT,
            GET,
            {'project_id': 'project_id'},
            None,
            HTTP_401_UNAUTHORIZED,
        ),
        (
            WORKER_CLIENT,
            DETAIL_PROJECT,
            GET,
            {'project_id': 'project_id'},
            None,
            HTTP_200_OK,
        ),
        (
            EMPLOYER_CLIENT,
            DETAIL_PROJECT,
            GET,
            {'project_id': 'project_id'},
            None,
            HTTP_200_OK,
        ),
        # Like: любой авторизованный может лайкнуть ---
        (
            ANONYMOUS_CLIENT,
            LIKE_PROJECT,
            POST,
            {'project_id': 'project_id'},
            None,
            HTTP_401_UNAUTHORIZED,
        ),
        (
            WORKER_CLIENT,
            LIKE_PROJECT,
            POST,
            {'project_id': 'project_id'},
            None,
            HTTP_200_OK,
        ),
        (
            EMPLOYER_CLIENT,
            LIKE_PROJECT,
            POST,
            {'project_id': 'project_id'},
            None,
            HTTP_400_BAD_REQUEST,
        ),
        # Response (отклик): только worker может откликнуться ---
        (
            ANONYMOUS_CLIENT,
            CREATE_RESPONSE,
            POST,
            {'project_id': 'project_id'},
            {'message': 'Interested'},
            HTTP_401_UNAUTHORIZED,
        ),
        (
            EMPLOYER_CLIENT,
            CREATE_RESPONSE,
            POST,
            {'project_id': 'project_id'},
            {'message': 'Not allowed'},
            HTTP_403_FORBIDDEN,
        ),
        (
            WORKER_CLIENT,
            CREATE_RESPONSE,
            POST,
            {'project_id': 'project_id'},
            {'message': 'Interested'},
            HTTP_201_CREATED,
        ),
        # Invite: только employer может приглашать ---
        (
            ANONYMOUS_CLIENT,
            INVITE_TO_PROJECT,
            POST,
            {'project_id': 'project_id', 'user_id': 'user_id'},
            None,
            HTTP_401_UNAUTHORIZED,
        ),
        (
            WORKER_CLIENT,
            INVITE_TO_PROJECT,
            POST,
            {'project_id': 'project_id', 'user_id': 'user_id'},
            None,
            HTTP_403_FORBIDDEN,
        ),
        (
            EMPLOYER_CLIENT,
            INVITE_TO_PROJECT,
            POST,
            {'project_id': 'project_id', 'user_id': 'user_id'},
            None,
            HTTP_200_OK,
        ),
        # Delete: только автор (employer) может удалить ---
        (
            ANONYMOUS_CLIENT,
            DETAIL_PROJECT,
            DELETE,
            {'project_id': 'project_id'},
            None,
            HTTP_401_UNAUTHORIZED,
        ),
        (
            WORKER_CLIENT,
            DETAIL_PROJECT,
            DELETE,
            {'project_id': 'project_id'},
            None,
            HTTP_403_FORBIDDEN,
        ),
        (
            EMPLOYER_CLIENT,
            DETAIL_PROJECT,
            DELETE,
            {'project_id': 'project_id'},
            None,
            HTTP_204_NO_CONTENT,
        ),
    ],
)
def test_project_endpoints_access(
    client_fixture: str,
    url_name: str,
    method: str,
    url_kwargs: dict,
    payload: Optional[dict],
    expected_status: int,
    request: pytest.FixtureRequest,
    project_id: str,
    user_id_worker: str,
) -> None:
    """Тест проверяет доступность эндпоинтов для юзеров."""
    if 'project_id' in str(url_kwargs):
        url_kwargs['project_id'] = project_id
    if 'user_id' in str(url_kwargs):
        url_kwargs['user_id'] = user_id_worker
    client = request.getfixturevalue(client_fixture)
    url = reverse(f'projects:{url_name}', kwargs=url_kwargs)
    call = getattr(client, method)
    response = call(
        url,
        data=payload,
        format='json',
    ) if payload is not None else call(url, format='json')
    if response.status_code != expected_status:
        print(
            f'\nОшибка: {client_fixture} | {url_name} | {method} | вернул '
            f'{response.status_code}, а должен был {expected_status}',
        )
        if hasattr(response, 'data'):
            print('Response data:', response.data)
    assert response.status_code == expected_status
