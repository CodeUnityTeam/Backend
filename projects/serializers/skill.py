from rest_framework import serializers

from users.models import Skill


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения и привязки навыков пользователя."""

    class Meta:
        model = Skill
        fields = ('skill_id', 'name')
        read_only_fields = ('name',)


class SkillIdSerializer(serializers.Serializer):
    """Сериализатор для передачи skill_id в теле запроса."""

    skill_id = serializers.UUIDField(
        help_text='UUID навыка',
    )
