from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from qna.models import Answer, AnswerLike
from qna.serializers.answer import AnswerDetailSerializer
from qna.serializers.like import LikeSerializer


@extend_schema_view(
    destroy=extend_schema(tags=['Answers'], summary='Удалить ответ'),
    like=extend_schema(
        tags=['Likes'],
        summary='Лайк/снятие лайка ответа',
        request=None,
        responses=LikeSerializer(),
    ),
)
class AnswerViewSet(DestroyModelMixin, GenericViewSet):
    """Представление для ответов."""

    # TODO [QNA]: Отсутствует проверка прав на удаление ответа.
    #   AnswerViewSet (строка 22) использует DestroyModelMixin, но нет
    #   permission_classes и нет проверки, что удалять ответ может только
    #   автор ответа или модератор.
    #   Любой аутентифицированный пользователь может отправить DELETE
    #   на /api/answers/{id}/ и удалить чужой ответ.
    #   Решение: добавить кастомное permission или переопределить
    #   perform_destroy с проверкой прав.

    queryset = Answer.objects.all()
    serializer_class = AnswerDetailSerializer

    # TODO [QNA]: Заменить ручную toggle-логику лайка на единый сервис
    #   с F()-инкрементом и добавить permission_classes.
    #   Проблемы:
    #     1. Дублирование логики с QuestionViewSet.like (question.py:177).
    #     2. answer.likes.count() — отдельный SQL-запрос после каждого лайка.
    #     3. Нет permission_classes — любой (в т.ч. аноним) может лайкать.
    #
    #   Решение через единый сервис + F():
    #   1. Создать единый сервис для лайков:
    #      # qna/services.py
    #      from django.db.models import F, Model
    #
    #      def toggle_like(
    #          like_model: type[Model],
    #          target_model: type[Model],
    #          target_obj: Model,
    #          user: Model,
    #          target_field: str,
    #      ) -> dict:
    #          """Универсальный toggle-лайк с F()-инкрементом."""
    #          like, created = like_model.objects.get_or_create(
    #              **{target_field: target_obj, 'user': user},
    #          )
    #          if not created:
    #              like.delete()
    #              target_model.objects.filter(pk=target_obj.pk).update(
    #                  likes_count=F('likes_count') - 1,
    #              )
    #              liked = False
    #          else:
    #              target_model.objects.filter(pk=target_obj.pk).update(
    #                  likes_count=F('likes_count') + 1,
    #              )
    #              liked = True
    #          target_obj.refresh_from_db(fields=['likes_count'])
    #          return {'liked': liked, 'likes_count': target_obj.likes_count}
    #
    #   2. В AnswerViewSet и QuestionViewSet использовать единый сервис:
    #      from qna.services import toggle_like
    #
    #      @action(detail=True, methods=['post'], url_path='like')
    #      def like(self, request, *args, **kwargs):
    #          answer = self.get_object()
    #          result = toggle_like(
    #              like_model=AnswerLike,
    #              target_model=Answer,
    #              target_obj=answer,
    #              user=request.user,
    #              target_field='answer',
    #          )
    #          return Response(result)
    #
    #   3. Добавить permission_classes:
    #      permission_classes = [IsAuthenticated]
    #
    #   Преимущества:
    #     - Единая логика для QuestionLike и AnswerLike.
    #     - F()-инкремент атомарен — нет гонки данных.
    #     - Нет отдельного SELECT для подсчёта лайков.
    #     - permission_classes защищают от анонимных запросов.
    #     - Убирается дублирование кода в 2-х местах.
    @extend_schema(
            tags=['Answers'],
            summary='Лайк/снятие лайка ответа',
        )
    @action(detail=True, methods=['post'], url_path='like')
    def like(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Ставит или снимает лайк на ответ."""
        answer = self.get_object()
        user = request.user
        like, created = AnswerLike.objects.get_or_create(
            answer=answer,
            user=user,
        )
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({
            'liked': liked,
            'likes_count': answer.likes.count(),
        })
