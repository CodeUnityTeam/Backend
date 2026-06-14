from django.db.models import (
    Case,
    Count,
    Prefetch,
    Q,
    Value,
    When,
)
from django.db.models.functions import Concat
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from qna.models import Answer, Question, QuestionLike
from qna.services import toggle_like
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
class QuestionViewSet(viewsets.ModelViewSet):
    """Представление для вопросов."""

    queryset = Question.objects.select_related('user').prefetch_related(
        Prefetch(
            'answers',
            queryset=Answer.objects.select_related('user').prefetch_related(
                'images',
            ).filter(is_active=True),
        ),
        'likes',
        'images',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        answers_count=Count(
            'answers',
            filter=Q(answers__is_active=True),
        ),
        author_name=Case(
            When(
                is_anonymous=True,
                then=Value('Аноним'),
            ),
            default=Concat(
                'user__first_name',
                Value(' '),
                'user__last_name',
            ),
        ),
    )
    # Лёгкий queryset для actions, где не нужны prefetch (add_answer, like)
    _light_queryset = Question.objects.only('pk')

    serializer_class = QuestionCreateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Получает класс сериализатора."""
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'retrieve':
            return QuestionWithAnswersSerializer
        return QuestionCreateSerializer

    def get_queryset(self):
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
        question = self.get_object()
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
        question = self.get_object()
        result = toggle_like(
            like_model=QuestionLike,
            target_obj=question,
            user=request.user,
            target_field='question',
        )
        return Response(result)
