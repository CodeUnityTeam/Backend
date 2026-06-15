from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet

from projects.serializers import SkillSerializer
from users.models import Skill


@extend_schema_view(
    list=extend_schema(tags=['Tags'], summary='Список тегов (скиллов)'),
)
class SkillViewSet(ListModelMixin, GenericViewSet):
    """Представление для Тегов (скиллов)."""

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
