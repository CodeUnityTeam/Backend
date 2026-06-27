from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from qna.models import AnswerLike
from qna.permissions import CanDeleteAnswer
from qna.selectors import get_answer_detail_queryset
from qna.serializers.answer import AnswerDetailSerializer
from qna.serializers.like import LikeSerializer
from qna.services import toggle_like


@extend_schema_view(
    destroy=extend_schema(
        tags=['Answers'],
        summary='Удалить ответ',
        description='Удалить ответ. Доступно только автору ответа.',
    ),
    like=extend_schema(
        tags=['Likes'],
        summary='Лайк/снятие лайка ответа',
        request=None,
        responses=LikeSerializer(),
    ),
)
class AnswerViewSet(DestroyModelMixin, GenericViewSet):
    """Представление для ответов."""

    serializer_class = AnswerDetailSerializer
    permission_classes = [IsAuthenticated, CanDeleteAnswer]

    def get_queryset(self) -> QuerySet:
        """Возвращает оптимизированный queryset с аннотациями."""
        return get_answer_detail_queryset()

    @extend_schema(
            tags=['Answers'],
            summary='Лайк/снятие лайка ответа',
            description='Ставит или снимает лайк на ответ.',
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
        result = toggle_like(
            like_model=AnswerLike,
            target_obj=answer,
            user=request.user,
            target_field='answer',
        )
        return Response(result)
