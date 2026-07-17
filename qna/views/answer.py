import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from qna.models import AnswerLike
from qna.permissions import CanUpdateDeleteQNA
from qna.selectors import get_answer_detail_queryset
from qna.serializers.answer import AnswerDetailSerializer
from qna.serializers.like import LikeSerializer
from qna.services import toggle_like

logger = logging.getLogger(__name__)


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

    queryset = get_answer_detail_queryset()
    serializer_class = AnswerDetailSerializer
    permission_classes = (IsAuthenticated, CanUpdateDeleteQNA)

    def get_permissions(self) -> list:
        """Возвращает permissions в зависимости от действия."""
        if self.action == 'like':
            return [IsAuthenticated()]
        return super().get_permissions()

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
        result = toggle_like(
            like_model=AnswerLike,
            target_obj=answer,
            user=request.user,
            target_field='answer',
        )
        logger.info(
            'Статус лайка для ответа изменён: user_id=%s, answer_id=%s, '
            'liked=%s.',
            request.user.user_id,
            answer.answer_id,
            result['liked'],
        )
        return Response(result)
