from rest_framework import serializers

from core.validators import file_validator
from minio.s3_utils import MediaType


class FileUploadSerializer(serializers.Serializer):
    """Сериализатор для валидации загружаемого файла."""

    file: serializers.ImageField = serializers.ImageField(
        write_only=True,
        validators=[file_validator(MediaType.UPLOAD_IMAGE)],
    )


class FileUploadResponseSerializer(serializers.Serializer):
    """Сериализатор ответа на загрузку файла."""

    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()
