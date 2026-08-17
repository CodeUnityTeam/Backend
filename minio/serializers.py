from typing import Any

from rest_framework import serializers

from minio.s3_utils import MediaType, S3Service


class PresignedPostRequestSerializer(serializers.Serializer):
    """Валидация параметров для генерации Presigned URL."""

    media_type = serializers.ChoiceField(
        choices=[(tag.value, tag.name) for tag in MediaType],
        label='Целевой бакет',
    )
    filename = serializers.CharField(
        max_length=255,
        label='Имя файла',
    )
    content_type = serializers.CharField(
        max_length=100,
        label='MIME-тип файла',
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверяет MIME-тип по белому списку бакета из .env."""
        media_type = MediaType(attrs['media_type'])
        content_type = attrs['content_type']

        if not S3Service.is_allowed_type(media_type, content_type):
            raise serializers.ValidationError(
                {
                    'content_type': (
                        f'Тип данных "{content_type}" не разрешен '
                        f'для раздела "{media_type.value}".'
                    ),
                },
            )
        return attrs


class PresignedPostResponseSerializer(serializers.Serializer):
    """Структура ответа с данными для прямой загрузки в S3."""

    url = serializers.URLField(
        help_text='URL адрес MinIO/S3 для отправки файла.',
    )
    fields = serializers.DictField(
        help_text='Скрытые поля политики безопасности и подписи.',
    )
    object_key = serializers.CharField(
        help_text='Сгенерированный бэкендом уникальный ключ файла.',
    )
    public_url = serializers.URLField(
        help_text='Будущий публичный URL файла после успешной загрузки.',
    )
