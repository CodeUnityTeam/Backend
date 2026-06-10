import uuid

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404

from core.constants.projects import APPLICANT, MEMBER, PENDING, PUBLISHED

from .models import Project, ProjectParticipant, Response

User = get_user_model()


def get_project_or_404(project_id: str) -> Project:
    """Получает проект по ID или выбрасывает 404, если не найден."""
    return get_object_or_404(Project, project_id=project_id)


def get_user_or_404(user_id: uuid) -> User:
    """Получает юзера по ID или выбрасывает 404, если не найден."""
    return get_object_or_404(User, user_id=user_id)


def get_project_with_relations(project_id: uuid) -> Project:
    """Возвращает проект с загруженными связанными объектами.

    - author (через select_related)
    - skills, specializations, project_format (через prefetch_related)
    """
    return Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
    ).get(project_id=project_id)


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


def get_optimized_project_queryset() -> QuerySet[Project]:
    """Возвращает оптимизированный queryset проектов с связанными данными."""
    return Project.objects.select_related(
        'author',
    ).prefetch_related(
        'skills',
        'specializations',
        'project_format',
        'participants',
        'likes',
        'responses',
    )


def add_user_to_project_participants(
    project: Project,
    user: User,
    status: str = MEMBER,
) -> ProjectParticipant:
    """Добавляет пользователя в участники проекта."""
    return ProjectParticipant.objects.get_or_create(
        project=project,
        user=user,
        status_participant=status,
    )


def get_response_feed_queryset(user: User) -> QuerySet:
    """Возвращает базовый queryset для ленты откликов текущего пользователя.

    user (User): текущий пользователь
    QuerySet: отфильтрованный queryset откликов
    """
    return Response.objects.select_related(
        'project',
        'user',
    ).order_by('-created_at')


# TODO [PROJECTS]: Некорректный exclude в get_recommended_projects_queryset.
#   На строке 113: participants__status_participant=[PENDING] — передаётся
#   список, а должно быть строковое значение 'pending' (константа PENDING).
#   Из-за этого exclude не срабатывает корректно — проекты, где пользователь
#   имеет статус PENDING, не исключаются из рекомендаций.
#   Решение: заменить [PENDING] на PENDING (убрать список).
# TODO [PROJECTS]: Дублирование логики get_project_or_404.
#   Функция (строка 15) дублирует стандартный get_object_or_404 без какой-либо
#   дополнительной логики. Используется в serializers.py и views.py.
#   Либо удалить и использовать get_object_or_404 напрямую, либо добавить
#   select_related/prefetch_related для оптимизации.
def get_recommended_projects_queryset(user: User) -> QuerySet[Project]:
    """Формирует QuerySet проектов для рекомендаций пользователю.

    Формируется на основе скиллов пользователя, которые совпадают с скиллами,
    требуемыми для выполнения проекта.

    - Показываем проекты со статусом PUBLISHED.
    - Исключаем проекты пользователя.
     - Исключаем проекты, где пользователь уже участник.
    """
    user_skill_ids = [skill.skill_id for skill in user.skills.all()]
    if not user_skill_ids:
        return Project.objects.none()
    # queryset с подсчётом совпадающих навыков
    recommended = Project.objects.filter(
        skills__skill_id__in=user_skill_ids,
        status_project=PUBLISHED,
    ).distinct()
    return recommended.exclude(
        participants__user=user,
        participants__status_participant=[PENDING],
    )


# TODO [PROJECTS]: Заменить ручную apply_sorting на стандартный
#   DRF OrderingFilter + django-filter OrderingFilter.
#   Проблема: apply_sorting (строка 129) вручную:
#     1. Аннотирует likes_count=Count('likes') для каждого вызова.
#     2. Проверяет sort_by на 'like', 'relevance', 'published_at'.
#     3. Вручную строит SearchVector/SearchRank для сортировки по релевантности.
#     4. Вызывается вручную в ProjectViewSet.list() после фильтрации.
#   Это дублирует стандартный OrderingFilter из DRF.
#
#   Решение через стандартный DRF + django-filter:
#   1. В ProjectViewSet добавить filter_backends:
#      from rest_framework.filters import OrderingFilter
#      from django_filters.rest_framework import DjangoFilterBackend
#
#      class ProjectViewSet(ModelViewSet):
#          filter_backends = [DjangoFilterBackend, OrderingFilter]
#          filterset_class = ProjectFilter
#          ordering_fields = ['published_at', 'likes_count']
#          ordering = ['-published_at']
#
#   2. В ProjectFilter добавить кастомный OrderingFilter для 'relevance':
#      class ProjectFilter(django_filters.FilterSet):
#          sort_by = django_filters.OrderingFilter(
#              fields=(
#                  ('-published_at', 'published_at'),
#                  ('-likes_count', 'like'),
#                  ('-rank', 'relevance'),
#              ),
#          )
#
#          def filter_queryset(self, queryset):
#              # Если sort_by=relevance и есть search — аннотируем rank
#              sort_by = self.data.get('sort_by')
#              search = self.data.get('search')
#              if sort_by == 'relevance' and search:
#                  vector = SearchVector('title', weight='A') + SearchVector(
#                      'short_desc', weight='B',
#                  )
#                  queryset = queryset.annotate(
#                      rank=SearchRank(vector, SearchQuery(search)),
#                  )
#              return super().filter_queryset(queryset)
#
#   3. Удалить apply_sorting() из selectors.py.
#   4. Удалить ручной вызов apply_sorting() из ProjectViewSet.list().
#
#   Преимущества:
#     - Декларативное описание через ordering_fields.
#     - OrderingFilter автоматически валидирует поля сортировки.
#     - Аннотация likes_count=Count('likes') выносится в get_queryset.
#     - SearchVector/SearchRank для релевантности — только при необходимости.
#     - Убирается ручная функция apply_sorting().
def apply_sorting(
    queryset: QuerySet,
    sort_by: str,
    search_query: str = None,
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
