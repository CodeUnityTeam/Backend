from rest_framework import serializers


class DocumentOutSerializer(serializers.Serializer):
    """Сериализатор для ответа со списком документов."""

    slug = serializers.CharField()
    title = serializers.CharField()
    file_url = serializers.URLField(read_only=True)
