from typing import Any

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from minio.s3_utils import MediaType, S3Service
from minio.serializers import (
    PresignedPostRequestSerializer,
)


class PresignedPostURLAPIView(APIView):
    """APIView для генерации ссылки прямой загрузки в S3/MinIO."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary='Получить URL для прямой загрузки файла в S3 (MinIO)',
        description=(
            '### Инструкция по интеграции на фронтенде:\n\n'
            '1. Отправьте `POST`-запрос, передав `media_type`, `filename` '
            'и `content_type`.\n'
            '2. Перенесите в объект `FormData` **абсолютно все** ключи '
            'и значения из полученного словаря `fields`.\n'
            '3. **КРИТИЧЕСКИ ВАЖНО:** Самым последним полем добавьте в '
            '`FormData` ваш файл, назвав ключ строго `"file"`. Иначе MinIO '
            'вернет 403 ошибку подписи.\n'
            '4. Отправьте `POST`-запрос с этой `FormData` на адрес `url`. '
            'MinIO вернет статус **204 No Content** при успехе.\n'
            '5. Будущий публичный URL файла для сохранения в базу '
            'лежит в поле `public_url`.'
        ),
        # Инлайн-описание структуры запроса
        request=inline_serializer(
            name='PresignedPostRequest',
            fields={
                'media_type': serializers.ChoiceField(
                    choices=[(tag.value, tag.name) for tag in MediaType],
                    help_text='Целевой бакет для загрузки файла.',
                ),
                'filename': serializers.CharField(
                    help_text='Имя файла (пример: photo.jpg).',
                ),
                'content_type': serializers.CharField(
                    help_text='MIME-тип (пример: image/png).',
                ),
            },
        ),
        # Инлайн-описание структуры ответа с красивым примером
        responses={
            200: inline_serializer(
                name='PresignedPostResponse',
                fields={
                    'url': serializers.URLField(),
                    'fields': serializers.DictField(
                        child=serializers.CharField(),
                        help_text='Поля политики безопасности и подписи.',
                    ),
                    'object_key': serializers.CharField(),
                    'public_url': serializers.URLField(),
                },
            ),
        },
        examples=[
            OpenApiExample(
                name='Пример успешного ответа контракта S3',
                value={
                    'url': 'http://127.0.0.1:9000/avatars',
                    'fields': {
                        'Content-Type': 'image/png',
                        'key': 'avatars/53091e6436ac4093bb.png',
                        'AWSAccessKeyId': 'minio_admin',
                        'policy': 'eyJleHBpcmF0aW9uIjogIjIwMjYt...',
                        'signature': 'eKqbZriWklvycxqld7lA7q1xkIw=',
                    },
                    'object_key': 'avatars/53091e6436ac4093bb.png',
                    'public_url': (
                        'http://127.0.0.1/avatars/53091e6436ac4093bb.png'
                    ),
                },
                status_codes=['200'],
            ),
        ],
        tags=['Files'],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Обработка запроса на генерацию Presigned POST."""
        serializer = PresignedPostRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        media_type = MediaType(serializer.validated_data['media_type'])
        filename = serializer.validated_data['filename']
        content_type = serializer.validated_data['content_type']

        payload = S3Service.generate_presigned_post_url(
            media_type=media_type,
            filename=filename,
            content_type=content_type,
        )

        return Response(payload, status=status.HTTP_200_OK)
