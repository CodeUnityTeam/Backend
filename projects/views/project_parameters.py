from drf_spectacular.utils import OpenApiParameter

from core.constants.projects import MAX_PAGE_SIZE, PAGE_SIZE

# Параметры вью для проектов в списке
PROJECT_LIST_PARAMETERS = [
    OpenApiParameter(
        name='format_id',
        type=str,
        location=OpenApiParameter.QUERY,
        description='Список ID форматов через запятую',
        required=False,
    ),
    OpenApiParameter(
        name='duration_operator',
        type=str,
        location=OpenApiParameter.QUERY,
        description=(
            'Оператор: less (меньше), '
            'greater (больше), '
            'between (между)'
        ),
        required=False,
        enum=['less', 'greater', 'between'],
    ),
    OpenApiParameter(
        name='spec_id',
        type=str,
        location=OpenApiParameter.QUERY,
        description='Список ID специализаций через запятую',
        required=False,
    ),
    OpenApiParameter(
        name='skills_id',
        type=str,
        location=OpenApiParameter.QUERY,
        description='Список ID навыков через запятую',
        required=False,
    ),
    OpenApiParameter(
        name='search',
        type=str,
        location=OpenApiParameter.QUERY,
        description='Поиск по title и short_desc',
        required=False,
    ),
    OpenApiParameter(
        name='status',
        type=str,
        location=OpenApiParameter.QUERY,
        description=(
            'Статус проекта: draft, published, recruiting_closed. '
            'При фильтрации по специализации проекты со статусом '
            'recruiting_closed не отображаются.'
        ),
        required=False,
        enum=['draft', 'published', 'recruiting_closed'],
    ),
    OpenApiParameter(
        name='sort_by',
        type=str,
        location=OpenApiParameter.QUERY,
        description=(
            'Сортировка: like (по лайкам), '
            'published_at (по дате публикации), '
            'relevance (по релевантности — только при наличии search). '
            'По умолчанию: published_at.'
        ),
        required=False,
        enum=['like', 'relevance', 'published_at'],
    ),
    OpenApiParameter(
        name='my_project',
        type=bool,
        location=OpenApiParameter.QUERY,
        description=(
            'Проекты, где пользователь — автор или участник. '
            'Если автор: все проекты (кроме blocked, arhived). '
            'Если участник: только published или recruiting_closed.'
        ),
        required=False,
    ),
    OpenApiParameter(
        name='favourites',
        type=bool,
        location=OpenApiParameter.QUERY,
        description=(
            'Проекты, которые пользователь добавил в избранное. '
            'Избранные проекты могут быть только со статусами: '
            'published, recruiting_closed.'
        ),
        required=False,
    ),
    OpenApiParameter(
        name='page',
        type=int,
        location=OpenApiParameter.QUERY,
        description='Номер страницы (по умолчанию 1)',
        required=False,
    ),
    OpenApiParameter(
        name='limit',
        type=int,
        location=OpenApiParameter.QUERY,
        description=(
            f'Записей на странице (по умолчанию {PAGE_SIZE}, '
            f'макс {MAX_PAGE_SIZE})'
        ),
        required=False,
    ),
    OpenApiParameter(
        name='load_more',
        type=bool,
        location=OpenApiParameter.QUERY,
        description='Флаг подгрузки (бесконечный скролл)',
        required=False,
    ),
]

# Параметры вью для проектов в рекоменадциях
PROJECT_RECOMENDATIONS_PARAMETERS = [
    OpenApiParameter(
        name='page',
        type=int,
        location=OpenApiParameter.QUERY,
        description='Номер страницы (по умолчанию 1)',
        required=False,
    ),
    OpenApiParameter(
        name='limit',
        type=int,
        location=OpenApiParameter.QUERY,
        description='Записей на странице (по умолчанию 20, макс 100)',
        required=False,
    ),
]
