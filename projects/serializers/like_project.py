from rest_framework import serializers


class ProjectLikeResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа после создания/удаления лайка."""

    liked = serializers.BooleanField()
    likes_count = serializers.IntegerField()
