from rest_framework import serializers


class FileUploadSerializer(serializers.Serializer):
    """Сериализатор для валидации загружаемого файла."""

    file: serializers.ImageField = serializers.ImageField(write_only=True)


class FileUploadResponseSerializer(serializers.Serializer):
    """Сериализатор ответа на загрузку файла."""

    image_id = serializers.UUIDField()
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()
