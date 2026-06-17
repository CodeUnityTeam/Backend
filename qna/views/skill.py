from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet

from projects.serializers import SkillSerializer
from qna.selectors import get_all_skills


@extend_schema_view(
    list=extend_schema(tags=['Tags'], summary='Список тегов (скиллов)'),
)
class SkillViewSet(ListModelMixin, GenericViewSet):
    """Представление для Тегов (скиллов)."""

    queryset = get_all_skills()
    serializer_class = SkillSerializer
