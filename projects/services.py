from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import Count, QuerySet

from core.constants.projects import APPLICANT, MEMBER, PENDING

from .models import Project, ProjectParticipant, Response

User = get_user_model()


def create_response(
    project: Project,
    user: User,
    initiator_type: str = APPLICANT,
    status_resp: str = PENDING,
) -> Response:
    """Создаёт новый отклик на проект."""
    return Response.objects.create(
        project=project,
        user=user,
        initiator_type=initiator_type,
        status_resp=status_resp,
    )


def add_user_to_project_participants(
    project: Project,
    user: User,
    status: str = MEMBER,
) -> ProjectParticipant:
    """Добавляет пользователя в участники проекта."""
    participant, _ = ProjectParticipant.objects.get_or_create(
        project=project,
        user=user,
        status_participant=status,
    )
    return participant


def apply_sorting(
    queryset: QuerySet,
    sort_by: str,
    search_query: str | None = None,
) -> QuerySet:
    """Применяет сортировку к queryset в зависимости от параметра sort_by.

    queryset: исходный queryset проектов.
    sort_by: параметр сортировки ('like', 'relevance', 'published_at').
    search_query: поисковый запрос (используется для релевантности).
    """
    annotated_qs = queryset.annotate(likes_count=Count('likes'))
    if sort_by == 'like':
        return annotated_qs.order_by('-likes_count')
    if sort_by == 'relevance' and search_query:
        search_vector = SearchVector('title', weight='A') + SearchVector(
            'short_desc',
            weight='B',
        )
        annotated_qs = annotated_qs.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query),
        )
        return annotated_qs.order_by('-rank')
    if sort_by == 'published_at':
        # Сортировка по дате публикации (сначала новые)
        return annotated_qs.order_by('-published_at')
    return annotated_qs.order_by('-published_at')
