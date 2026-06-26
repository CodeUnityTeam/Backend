from rest_framework import serializers


class ProjectFavoriteResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа после избранного."""

    favorited = serializers.BooleanField()
