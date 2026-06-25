import hashlib
from typing import Any

from django.core.cache import cache
from django.db.models import QuerySet
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import (
    CACHE_KEY_QNA_PREFIX,
    QUESTION_DETAIL_CACHE_TIMEOUT,
    QUESTION_LIST_CACHE_TIMEOUT,
)
from qna.models import QuestionLike
from qna.selectors import (
    get_light_question_queryset,
    get_question_detail_queryset,
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


@extend_schema_view(
    list=extend_schema(tags=['Questions'], summary='Список вопросов'),
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
    http_method_names = ['get', 'post', 'patch', 'delete']
    retrieve_cache_timeout = QUESTION_DETAIL_CACHE_TIMEOUT
    retrieve_cache_key_prefix = 'qna'

    def get_permissions(self):
        """Назначает разные права для разных действий.

        - list: любой пользователь (включая анонимных)
        - остальные действия: только авторизованные
        """
        if self.action == 'list':
            return (AllowAny(),)
        return (IsAuthenticated(),)

    def list(
        self, request: Request, *args: Any, **kwargs: Any,
    ) -> Response:
        """Кэширует список вопросов.

        Ключ: qna:list:{md5(params)} — без user_id, т.к. данные публичные
        (QuestionListSerializer не содержит персонализированных полей).
        """
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(
            str(sorted_params).encode(),
        ).hexdigest()
        cache_key = f'{CACHE_KEY_QNA_PREFIX}:list:{params_str}'

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=QUESTION_LIST_CACHE_TIMEOUT,
            )

        return response

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Получает класс сериализатора."""
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'retrieve':
            return QuestionWithAnswersSerializer
        return QuestionCreateSerializer

    def get_queryset(self) -> QuerySet:
        """Возвращает оптимизированный queryset в зависимости от action."""
        if self.action in ('add_answer', 'like'):
            return self._light_queryset
        return super().get_queryset()

    @extend_schema(
            request=QuestionCreateSerializer,
            responses=QuestionCreateResponseSerializer,
        )
    def create(self, request: Request) -> Response:
        """Создаёт вопрос."""
        serializer = QuestionCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
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
        serializer = QuestionUpdateSerializer(
            question,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
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
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Создаёт ответ на вопрос."""
        question = get_question_or_404(question_id=self.kwargs['pk'])
        serializer = AnswerCreateSerializer(
            data=request.data,
            context={'request': request, 'question': question},
        )
        serializer.is_valid(raise_exception=True)
        answer = serializer.save()
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
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Ставит или снимает лайк на вопрос."""
        question = get_question_or_404(question_id=self.kwargs['pk'])
        result = toggle_like(
            like_model=QuestionLike,
            target_obj=question,
            user=request.user,
            target_field='question',
        )
        return Response(result)
