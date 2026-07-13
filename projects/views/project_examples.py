from drf_spectacular.utils import OpenApiExample

BASE_PROJECT_RESPONSE = {
    'project_id': '79af30fc-e011-4a30-8592-2e115c4a2a50',
    'title': 'LifePlanner — приложение-органайзер',
    'short_desc': 'Мобильное приложение для планирования задач',
    'location': 'Москва',
    'status_project': 'published',
    'published_at': '2026-07-08T20:09:21+03:00',
    'participants_count': 1,
    'is_liked_by_me': False,
    'is_favorite_by_me': False,
    'skills': [
        {
            'skill_id': '040beef5-07e2-4f45-8292-5f46ef228568',
            'name': 'Flutter',
        },
        {
            'skill_id': '04198d0b-0aff-4067-9e26-d558c85e7b0a',
            'name': 'Dart',
        },
    ],
    'specializations': [
        {
            'spec_id': 'ebf19476-218f-491b-bd3b-b8cc8877321d',
            'name': 'Account Manager',
        },
        {
            'spec_id': 'eb943c2d-0859-4363-8884-c51d42b4a587',
            'name': 'Firmware Developer',
        },
    ],
    'project_format': [
        {
            'format_id': '450eab94-627f-4805-81b0-e8bcca4a0e7c',
            'name': 'Гибрид',
        },
    ],
    'participants': [
        {
            'user_id': '1fd641f6-1413-4021-948f-f6165562af70',
            'full_name': 'Анна Петрова',
            'avatar': 'https://...',
        },
        {
            'user_id': 'b04571cc-4442-483b-8593-3434fb7c657c',
            'full_name': 'Иван Иванов',
            'avatar': 'https://...',
        },
    ],
    'author': {
        'user_id': 'b04571cc-4442-483b-8593-3434fb7c657c',
        'full_name': 'Иван Иванов',
        'avatar': 'https://...',
        'last_activity_at': '2026-07-11T17:53:46.079975+03:00',
    },
}

EXAMPLE_DETAIL_RESPONSE_PROJECT = [
    OpenApiExample(
        'Обычный пользователь',
        summary='Обычный пользователь (не автор, не участник)',
        value=BASE_PROJECT_RESPONSE.copy(),
    ),
    OpenApiExample(
        'Автор проекта',
        summary='Автор проекта видит полные контакты участников',
        value={
            **BASE_PROJECT_RESPONSE,
            'full_desc': 'Полное описание проекта...',
            'participants': [
                {
                    **participant,
                    'email': (
                        f'{participant["full_name"].split()[0].lower()}'
                        '@example.com'
                    ),
                    'phone': '+79001234567',
                }
                for participant in BASE_PROJECT_RESPONSE['participants']
            ],
            'author': {
                **BASE_PROJECT_RESPONSE['author'],
                'email': 'ivan@example.com',
                'phone': '+79001112233',
            },
        },
    ),
    OpenApiExample(
        'Участник проекта',
        summary=(
            'Участник проекта видит контакты автора, но не других участников'
        ),
        value={
            **BASE_PROJECT_RESPONSE,
            'full_desc': 'Полное описание проекта бла бла',
            'participants': [
                {
                    **participant, 'avatar': participant.get(
                        'avatar',
                        'https://...',
                    ),
                }
                for participant in BASE_PROJECT_RESPONSE['participants']
            ],
            'author': {
                **BASE_PROJECT_RESPONSE['author'],
                'email': 'ivan@example.com',
                'phone': '+79001112233',
            },
        },
    ),
]
