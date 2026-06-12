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

    queryset = Answer.objects.all()
    serializer_class = AnswerDetailSerializer

    @extend_schema(
        tags=['Answers'],
        summary='Лайк/снятие лайка ответа',
    )
    @action(detail=True, methods=['post'], url_path='like')
    def like(
        self,
        request: Request,
        *args,
        **kwargs,
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
