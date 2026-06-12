from rest_framework import serializers

from users.models import Skill


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов(скиллов)."""

    id = serializers.UUIDField(source='skill_id')

    class Meta:
        model = Skill
        fields = ('id', 'name')
