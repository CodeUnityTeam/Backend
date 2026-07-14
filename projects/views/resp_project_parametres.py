from drf_spectacular.utils import OpenApiParameter, OpenApiTypes

RESPONSE_LIST_PARAMETERS = [
    OpenApiParameter(
        name='status',
        description='Фильтр по статусу отклика/приглашения',
        required=False,
        type=str,
        enum=['all', 'pending', 'approved', 'rejected', 'withdrawn'],
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='project_id',
        description='Фильтр по конкретному проекту',
        required=False,
        type=OpenApiTypes.UUID,
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='page',
        description='Номер страницы',
        required=False,
        type=int,
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='limit',
        description='Количество элементов на странице',
        required=False,
        type=int,
        location=OpenApiParameter.QUERY,
    ),
    OpenApiParameter(
        name='sort_order',
        description=(
            'Порядок сортировки по created_at.\n\n'
            'Допустимые значения:\n\n'
            '  • "asc" — по возрастанию (старые сначала)\n\n'
            '  • "desc" — по убыванию (новые сначала).\n\n'
            'По умолчанию — "desc".'
        ),
        required=False,
        type=str,
        enum=['asc', 'desc'],
        location=OpenApiParameter.QUERY,
    ),
]

RESPONSE_UPDATE_PARAMETER = [
    OpenApiParameter(
        name='response_id',
        type=OpenApiTypes.UUID,
        location=OpenApiParameter.PATH,
        description='ID отклика, который хотите изменить',
    ),
]

INVITE_RESPONSES_PARAMETER = [
    OpenApiParameter(
        name='user_id',
        type=OpenApiTypes.UUID,
        location=OpenApiParameter.PATH,
        description='ID пользователя, которого приглашают в проект',
    ),
]
