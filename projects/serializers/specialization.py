from rest_framework import serializers

from users.models import Specialization


class SpecializationSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения специализаций."""

    class Meta:
        model = Specialization
        fields = ('spec_id', 'name')
        read_only_fields = ('name',)


class SpecializationIdSerializer(serializers.Serializer):
    """Сериализатор для передачи spec_id в теле запроса."""

    spec_id = serializers.UUIDField(
        help_text='UUID специализации',
    )
