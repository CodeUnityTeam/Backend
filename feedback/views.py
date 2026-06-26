from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from feedback.serializers import FeedbackCreateSerializer


@extend_schema_view(
    create=extend_schema(tags=['Feedbacks'], summary='Дать обратную связь'),
)
class FeedbackViewSet(viewsets.ModelViewSet):
    """Представление для формы обратной связи."""

    permission_classes = [IsAuthenticated]
    http_method_names = ['post']

    @extend_schema(
        request=FeedbackCreateSerializer,
        responses=FeedbackCreateSerializer,
    )
    def create(self, request: Request) -> Response:
        """Создаёт обратную связь."""
        serializer = FeedbackCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        print('data = ', request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED,)
