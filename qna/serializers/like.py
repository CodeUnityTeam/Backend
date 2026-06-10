from rest_framework import serializers


class LikeSerializer(serializers.Serializer):
    """Сериализатор лайков."""

    liked = serializers.BooleanField()
    likes_count = serializers.IntegerField()
