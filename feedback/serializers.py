import logging
import uuid
from typing import Any, List

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from core.constants.feedback import (
    MAX_IMAGE_COUNT_FEEDBACK,
    MAX_IMAGE_SIZE_FEEDBACK,
)
from feedback.models import FeedbackForm, FeedbackImage, Review
from feedback.selectors import create_review
from feedback.services import feedback_image_upload_handler
from projects.serializers.specialization import SpecializationSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class DynamicHTTPValidationError(APIException):
    """Динамический преобразователь исключений."""

    def __init__(
            self, detail: dict,
            status_code: int,
            code: str | None = None,
    ) -> None:
        """Для разных кодов ошибок при валидации."""
        self.status_code = status_code
        super().__init__(detail, code)


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания отзыва."""

    class Meta:
        model = Review
        fields = (
            'text',
        )

    def create(self, validated_data: dict) -> Review:
        """Создаёт отзыв от текущего пользователя."""
        user = self.context['request'].user
        return create_review(user=user, text=validated_data['text'])


class ReviewBaseSerializer(serializers.ModelSerializer):
    """Базовый сериализатор отзыва с полями автора."""

    author_name = serializers.CharField(read_only=True)
    author_avatar = serializers.URLField(
        source='user.avatar_url',
        read_only=True,
    )
    author_specializations = SpecializationSerializer(
        many=True,
        source='user.specializations',
        read_only=True,
    )

    class Meta:
        model = Review
        fields = (
            'review_id',
            'author_name',
            'author_avatar',
            'author_specializations',
            'text',
            'created_at',
        )


class ReviewListSerializer(ReviewBaseSerializer):
    """Сериализатор для списка отзывов."""

    class Meta(ReviewBaseSerializer.Meta):
        pass


class ReviewDetailSerializer(ReviewBaseSerializer):
    """Сериализатор детального отзыва."""

    class Meta(ReviewBaseSerializer.Meta):
        fields = ReviewBaseSerializer.Meta.fields + ('updated_at',)


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления отзыва."""

    class Meta:
        model = Review
        fields = (
            'text',
        )


class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания обратной связи."""

    attachments = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = FeedbackForm
        fields = (
            'subject',
            'content',
            'attachments',
        )

    def create(self, validated_data: dict) -> FeedbackForm:
        """Создание обратной связи."""
        attachments = validated_data.pop('attachments', [])
        user = self.context['request'].user
        logger.info(
            'Создание обратной связи: user_id=%s, subject=%s, files=%d',
            user.user_id,
            validated_data.get('subject'),
            len(attachments),
        )
        with transaction.atomic():
            feedback = FeedbackForm.objects.create(user=user, **validated_data)
            for image in attachments:
                FeedbackImage.objects.create(
                    feedback=feedback,
                    uploaded_by=user,
                    image_id=uuid.uuid4(),
                    image_url=feedback_image_upload_handler(file_obj=image),
                    original_name=image.name,
                    file_size=image.size,
                    mime_type=image.content_type.split('/')[1],
                )
        logger.info(
            'Обратная связь успешно создана: user_id=%s, feedback_id=%s, '
            'files=%d',
            user.user_id,
            feedback.feedback_id,
            len(attachments),
        )
        return feedback

    def validate_attachments(self, value: List) -> List[Any]:
        """Валидация изображений прикреплённых к форме обратной связи.

        Выполняет следующие проверки:
        - Количество - не более 5.
        - Размер каждого изображения - не более 5 МБ.
        - Формат изображений - только JPEG/PNG.
        """
        if len(value) > MAX_IMAGE_COUNT_FEEDBACK:
            raise DynamicHTTPValidationError(
                detail={'error': 'Количество изображений не должно '
                        'превышать 5 шт.'},
                status_code=status.HTTP_400_BAD_REQUEST,
                code='max_limit_exceeded',
            )
        for image in value:
            if image.content_type.split('/')[1] not in ('jpeg', 'png'):
                raise DynamicHTTPValidationError(
                    detail={'error': 'Неподдерживаемый тип файла. Пожалуйста, '
                            'загрузите файл в формате png либо jpeg.'},
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
            if image.size > MAX_IMAGE_SIZE_FEEDBACK:
                raise DynamicHTTPValidationError(
                    detail={'error': 'Файл слишком большой. Максимально '
                            'допустимый размер - 5 Мб. Пожалуйста, уменьшите '
                            'размер файла и попробуйте снова.'},
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
        return value
