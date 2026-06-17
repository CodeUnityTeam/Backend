from rest_framework import serializers

from projects.models import WorkFormat


class WorkFormatSerializer(serializers.ModelSerializer):
    """Сериализатор форматов работы."""

    class Meta:
        model = WorkFormat
        fields = ('format_id', 'name')
        read_only_fields = ('name',)
        extra_kwargs = {
            'format_id': {'read_only': False},
        }
