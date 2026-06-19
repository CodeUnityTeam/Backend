from rest_framework import serializers


class FeedbackFileUploadSerializer(serializers.Serializer):
    """Сериализатор для валидации загружаемого файла обратной связи."""

    file: serializers.ImageField = serializers.ImageField(write_only=True)


class FeedbackFileUploadResponseSerializer(serializers.Serializer):
    """Сериализатор ответа на загрузку файла для обратной связи."""

    image_id = serializers.UUIDField()
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()