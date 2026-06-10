from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from qna.models import (
    Question,
    QuestionLike,
)
from qna.serializers.answer import (
    AnswerCreateResponseSerializer,
    AnswerCreateSerializer,
    AnswerDetailSerializer,
)
from qna.serializers.like import LikeSerializer
from qna.serializers.question import (
    QuestionCreateResponseSerializer,
    QuestionCreateSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
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

    # TODO [QNA-14/19]: Заменить ручной retrieve на стандартный DRF retrieve
    #   с аннотациями и prefetch_related.
    #   Проблема: retrieve (строка 86) вручную:
    #     1. Вызывает self.get_object() — получает вопрос без prefetch_related.
    #     2. Вручную фильтрует question.answers.filter(is_active=True).
    #     3. Вручную сериализует question и answers отдельно.
    #     4. Вручную формирует Response с двумя ключами.
    #   При этом:
    #     - Нет select_related('user') — N+1 на author_name.
    #     - Нет prefetch_related('answers__images') — N+1 на images ответов.
    #     - Нет аннотации likes_count/answers_count — N+1 в сериализаторах.
    #
    #   Решение через стандартный DRF:
    #   1. Оптимизировать queryset:
    #      from django.db.models import Count, Q, Prefetch
    #
    #      class QuestionViewSet(ModelViewSet):
    #          queryset = Question.objects.select_related('user').prefetch_related(
    #              Prefetch(
    #                  'answers',
    #                  queryset=Answer.objects.select_related('user').prefetch_related(
    #                      'images',
    #                  ),
    #                  queryset=Answer.objects.filter(is_active=True),
    #              ),
    #              'likes',
    #              'images',
    #          ).annotate(
    #              likes_count=Count('likes', distinct=True),
    #              answers_count=Count('answers', filter=Q(answers__is_active=True)),
    #          )
    #
    #   2. В QuestionDetailSerializer заменить SerializerMethodField на IntegerField:
    #      likes_count = serializers.IntegerField(read_only=True)
    #      answers_count = serializers.IntegerField(read_only=True)
    #
    #   3. В QuestionListSerializer заменить SerializerMethodField на IntegerField:
    #      likes_count = serializers.IntegerField(read_only=True)
    #      answers_count = serializers.IntegerField(read_only=True)
    #
    #   4. В retrieve использовать стандартный Response с сериализатором,
    #      который включает answers как nested field:
    #
    #      class QuestionWithAnswersSerializer(serializers.ModelSerializer):
    #          """Объединяет вопрос и ответы в один ответ."""
    #          answers = AnswerDetailSerializer(many=True, read_only=True)
    #
    #          class Meta:
    #              model = Question
    #              fields = QuestionDetailSerializer.Meta.fields + ('answers',)
    #
    #      def retrieve(self, request, *args, **kwargs):
    #          question = self.get_object()
    #          serializer = QuestionWithAnswersSerializer(question)
    #          return Response(serializer.data)
    #
    #   Преимущества:
    #     - Все данные загружаются за 3 SQL-запроса (вопрос + ответы + изображения).
    #     - Аннотации на уровне БД — не нужно считать в Python.
    #     - Prefetch с фильтром is_active=True — не нужно фильтровать вручную.
    #     - Единый сериализатор вместо ручного формирования Response.
    #     - select_related('user') — нет N+1 на author_name.

    queryset = Question.objects.all()
    serializer_class = QuestionCreateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Получает класс сериализатора."""
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'retrieve':
            return QuestionDetailSerializer
        return QuestionCreateSerializer

    @extend_schema(
        responses=inline_serializer(
            name='QuestionRetrieveResponse',
            fields={
                'question': QuestionDetailSerializer(),
                'answers': AnswerDetailSerializer(many=True),
            },
        ),
    )
    def retrieve(
        self,
        request: Request,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> Response:
        """Возвращает детальную страницу вопроса."""
        question = self.get_object()
        answers = question.answers.filter(is_active=True)
        return Response({
            'question': QuestionDetailSerializer(question).data,
            'answers': AnswerDetailSerializer(answers, many=True).data,
        })

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
        request=QuestionCreateSerializer,
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
        serializer = QuestionCreateSerializer(
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

    # TODO [QNA-15/19]: Заменить ручной подсчёт лайков на F()-инкремент.
    #   Проблема: в like (строка 177) после создания/удаления лайка делается
    #   question.likes.count() — отдельный SQL-запрос для подсчёта.
    #   Аналогичная проблема в AnswerViewSet.like.
    #
    #   Решение через стандартный F()-инкремент:
    #   1. Добавить поле likes_count в модель Question:
    #      class Question(models.Model):
    #          likes_count = models.IntegerField(default=0)
    #
    #   2. В action like() использовать F() для атомарного обновления:
    #      from django.db.models import F
    #
    #      @action(detail=True, methods=['post'], url_path='like')
    #      def like(self, request, *args, **kwargs):
    #          question = self.get_object()
    #          user = request.user
    #          like, created = QuestionLike.objects.get_or_create(
    #              question=question, user=user,
    #          )
    #          if not created:
    #              like.delete()
    #              Question.objects.filter(pk=question.pk).update(
    #                  likes_count=F('likes_count') - 1,
    #              )
    #              liked = False
    #          else:
    #              Question.objects.filter(pk=question.pk).update(
    #                  likes_count=F('likes_count') + 1,
    #              )
    #              liked = True
    #          question.refresh_from_db(fields=['likes_count'])
    #          return Response({
    #              'liked': liked,
    #              'likes_count': question.likes_count,
    #          })
    #
    #   Преимущества:
    #     - F()-инкремент атомарен — нет гонки данных при конкурентных запросах.
    #     - Нет отдельного SELECT для подсчёта — читаем из поля модели.
    #     - Денормализация оправдана для частых операций чтения (список вопросов).
    #     - refresh_from_db() обновляет только одно поле — минимальная нагрузка.
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
        user = request.user
        like, created = QuestionLike.objects.get_or_create(
            question=question,
            user=user,
        )
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({
            'liked': liked,
            'likes_count': question.likes.count(),
        })
