import logging
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException

from core.constants.feedback import (
    MAX_CONTENT_FEEDBACK,
    MAX_IMAGE_COUNT_FEEDBACK,
    MAX_SUBJECT_FEEDBACK,
    MIN_CONTENT_FEEDBACK,
    MIN_SUBJECT_FEEDBACK,
)
from core.validators import file_validator, validate_no_bad_words
from feedback.models import FeedbackForm, FeedbackImage, Review
from feedback.selectors import create_review
from feedback.services import feedback_image_upload_handler
from minio.s3_utils import MediaType
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

    subject = serializers.CharField(
        min_length=MIN_SUBJECT_FEEDBACK,
        max_length=MAX_SUBJECT_FEEDBACK,
        validators=[validate_no_bad_words],
    )
    content = serializers.CharField(
        min_length=MIN_CONTENT_FEEDBACK,
        max_length=MAX_CONTENT_FEEDBACK,
        validators=[validate_no_bad_words],
    )
    attachments = serializers.ListField(
        child=serializers.ImageField(
            validators=[file_validator(MediaType.FEEDBACK_IMAGE)],
        ),
        max_length=MAX_IMAGE_COUNT_FEEDBACK,
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
