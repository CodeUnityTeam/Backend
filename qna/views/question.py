import hashlib
import logging
from typing import Any

from django.core.cache import cache
from django.db.models import Case, IntegerField, QuerySet, When
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response

from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import (
    CACHE_KEY_QNA_PREFIX,
    QUESTION_DETAIL_CACHE_TIMEOUT,
    QUESTION_LIST_CACHE_TIMEOUT,
)
from qna.filters import QuestionFilter
from qna.models import QuestionLike
from qna.paginations import CustomQuestionOffsetPagination
from qna.permissions import CanUpdateDeleteQNA
from qna.selectors import (
    get_light_question_queryset,
    get_question_detail_queryset,
    get_question_list_queryset,
    get_question_or_404,
)
from qna.serializers.answer import (
    AnswerCreateResponseSerializer,
    AnswerCreateSerializer,
)
from qna.serializers.like import LikeSerializer
from qna.serializers.question import (
    QuestionCreateResponseSerializer,
    QuestionCreateSerializer,
    QuestionListSerializer,
    QuestionUpdateSerializer,
    QuestionWithAnswersSerializer,
)
from qna.services import toggle_like

logger = logging.getLogger(__name__)


def _build_question_list_cache_key(request: Request) -> str | None:
    """Сформировать ключ полного упорядоченного списка ID вопросов.

    Параметры пагинации не входят в ключ: limit/offset применяются к уже
    закэшированному списку. Публичные фильтры используют общий ключ, а
    filter=my получает отдельный ключ текущего пользователя.
    """
    pagination_params = {'limit', 'offset'}
    normalized_params = sorted(
        (key, tuple(values))
        for key, values in request.query_params.lists()
        if key not in pagination_params
    )
    params_hash = hashlib.sha256(
        repr(normalized_params).encode('utf-8'),
    ).hexdigest()

    is_my_filter = request.query_params.get('filter') == 'my'
    if is_my_filter and not request.user.is_authenticated:
        return None

    cache_scope = 'public'
    if is_my_filter:
        cache_scope = str(request.user.pk)

    return (
        f'{CACHE_KEY_QNA_PREFIX}:list:ids:'
        f'{cache_scope}:{params_hash}'
    )


@extend_schema_view(
    list=extend_schema(
        tags=['Questions'],
        summary='Список вопросов',
        description=(
            'Возвращает список вопросов с пагинацией, поиском, '
            'фильтрам по тегам, по популярности, вопросы без ответов, '
            'вопросы пользователя '
            '(только для аунтетифицированных пользователей.)\n\n'
            '- Эндпоинт доступен любому пользователю, кроме фильтра "my"'
        ),
        parameters=[
            OpenApiParameter(
                name='tags',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Список ID навыков через запятую',
                required=False,
            ),
            OpenApiParameter(
                name='filter',
                description=(
                    'Варианты:'
                    'popular (по лайкам), '
                    'no_answers (без ответов), '
                    'my (мои вопросы)'
                ),
                enum=['popular', 'no_answers', 'my'],
                required=False,
                location=OpenApiParameter.QUERY,
                type=str,
            ),
        ],
    ),
    create=extend_schema(tags=['Questions'], summary='Создать вопрос'),
    retrieve=extend_schema(
        tags=['Questions'],
        summary='Детальная страница вопроса',
    ),
    partial_update=extend_schema(
        tags=['Questions'],
        summary='Редактировать вопрос',
    ),
    destroy=extend_schema(tags=['Questions'], summary='Удалить вопрос'),
)
class QuestionViewSet(CacheRetrieveMixin, viewsets.ModelViewSet):
    """Представление для вопросов."""

    queryset = get_question_detail_queryset()
    # Лёгкий queryset для actions, где не нужны prefetch (add_answer, like)
    _light_queryset = get_light_question_queryset()
    serializer_class = QuestionCreateSerializer
    http_method_names = ('get', 'post', 'patch', 'delete')
    retrieve_cache_timeout = QUESTION_DETAIL_CACHE_TIMEOUT
    retrieve_cache_key_prefix = 'qna'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = QuestionFilter
    pagination_class = CustomQuestionOffsetPagination

    def get_permissions(self) -> BasePermission:
        """Назначает разные права для разных действий.

        - list: любой пользователь (включая анонимных)
        - остальные действия: только авторизованные
        """
        if self.action in ('list', 'retrieve'):
            return (AllowAny(),)
        if self.action in ('partial_update', 'destroy'):
            return (CanUpdateDeleteQNA(),)
        return (IsAuthenticated(),)

    def list(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Вернуть вопросы, кэшируя полный упорядоченный список их ID."""
        if (
            request.query_params.get('filter') == 'my'
            and not request.user.is_authenticated
        ):
            raise NotAuthenticated('Authentication is required for filter=my.')
        cache_key = _build_question_list_cache_key(request)
        assert cache_key is not None
        cached_ids = cache.get(cache_key)

        logger.info(
            'Запрос списка вопросов: user_id=%s, params=%s, cache_key=%s.',
            (
                request.user.pk
                if request.user.is_authenticated
                else 'anonymous'
            ),
            request.query_params,
            cache_key,
        )

        if cached_ids is None:
            filtered_queryset = self.filter_queryset(self.get_queryset())
            ordered_ids = [
                str(question_id)
                for question_id in filtered_queryset.values_list(
                    'question_id',
                    flat=True,
                )
            ]
            cache.set(
                cache_key,
                ordered_ids,
                timeout=QUESTION_LIST_CACHE_TIMEOUT,
            )
            logger.info(
                'Cache MISS списка вопросов: cache_key=%s, total_ids=%d.',
                cache_key,
                len(ordered_ids),
            )
        else:
            ordered_ids = cached_ids
            logger.info(
                'Cache HIT списка вопросов: cache_key=%s, total_ids=%d.',
                cache_key,
                len(ordered_ids),
            )

        page_ids = self.paginate_queryset(ordered_ids)
        if not page_ids:
            logger.debug(
                'Страница списка вопросов пуста: offset=%s, limit=%s.',
                request.query_params.get('offset', 0),
                request.query_params.get('limit'),
            )
            return self.get_paginated_response([])

        preserved_order = Case(
            *[
                When(question_id=question_id, then=position)
                for position, question_id in enumerate(page_ids)
            ],
            output_field=IntegerField(),
        )
        page_queryset = (
            self.get_queryset()
            .filter(question_id__in=page_ids)
            .order_by(preserved_order)
        )
        serializer = self.get_serializer(page_queryset, many=True)

        logger.debug(
            'Список вопросов сформирован: cache_status=%s, '
            'offset=%s, page_size=%d, total_ids=%d.',
            'HIT' if cached_ids is not None else 'MISS',
            request.query_params.get('offset', 0),
            len(page_ids),
            len(ordered_ids),
        )
        return self.get_paginated_response(serializer.data)

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Получает класс сериализатора."""
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'retrieve':
            return QuestionWithAnswersSerializer
        return QuestionCreateSerializer

    def get_queryset(self) -> QuerySet:
        """Возвращает оптимизированный queryset в зависимости от action."""
        if self.action == 'list':
            return get_question_list_queryset()
        qs = super().get_queryset()
        if self.action in ('add_answer', 'like'):
            qs = self._light_queryset
        return qs

    @extend_schema(
        request=QuestionCreateSerializer,
        responses=QuestionCreateResponseSerializer,
    )
    def create(self, request: Request) -> Response:
        """Создаёт вопрос."""
        logger.info(
            'Запрос создания вопроса: user_id=%s.',
            request.user.user_id,
        )
        serializer = QuestionCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        logger.info(
            'Вопрос успешно создан: user_id=%s, question_id=%s.',
            request.user.user_id,
            question.question_id,
        )
        return Response(
            QuestionCreateResponseSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=QuestionUpdateSerializer,
        responses=QuestionCreateResponseSerializer,
    )
    def partial_update(
        self,
        request: Request,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> Response:
        """Обновляет вопрос частично."""
        question = self.get_object()
        logger.info(
            'Запрос частичного обновления вопроса: user_id=%s, '
            'question_id=%s.',
            request.user.user_id,
            question.question_id,
        )
        serializer = QuestionUpdateSerializer(
            question,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        logger.info(
            'Вопрос успешно обновлен: user_id=%s, question_id=%s.',
            request.user.user_id,
            question.question_id,
        )
        return Response(
            QuestionCreateResponseSerializer(question).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AnswerCreateSerializer,
        responses=AnswerCreateResponseSerializer,
        tags=['Answers'],
        summary='Создать ответ',
    )
    @action(detail=True, methods=['post'], url_path='answers')
    def add_answer(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs,  # noqa ANN:003
    ) -> Response:
        """Создаёт ответ на вопрос."""
        question = get_question_or_404(question_id=self.kwargs['pk'])
        logger.info(
            'Запрос создания ответа на вопрос: user_id=%s, question_id=%s.',
            request.user.user_id,
            question.question_id,
        )
        serializer = AnswerCreateSerializer(
            data=request.data,
            context={'request': request, 'question': question},
        )
        serializer.is_valid(raise_exception=True)
        answer = serializer.save()
        logger.info(
            'Ответ успешно создан: user_id=%s, question_id=%s, answer_id=%s.',
            request.user.user_id,
            question.question_id,
            answer.answer_id,
        )
        return Response(
            AnswerCreateResponseSerializer(answer).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=['Likes'],
        summary='Лайк/снятие лайка вопроса',
        request=None,
        responses=LikeSerializer(),
    )
    @action(detail=True, methods=['post'], url_path='like')
    def like(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs,  # noqa ANN:003
    ) -> Response:
        """Ставит или снимает лайк на вопрос."""
        question = get_question_or_404(question_id=self.kwargs['pk'])
        result = toggle_like(
            like_model=QuestionLike,
            target_obj=question,
            user=request.user,
            target_field='question',
        )
        logger.info(
            'Статус лайка для вопроса изменён: user_id=%s, question_id=%s, '
            'liked=%s.',
            request.user.user_id,
            question.question_id,
            result['liked'],
        )
        return Response(result)
