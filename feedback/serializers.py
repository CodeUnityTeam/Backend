import uuid
from typing import List

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.constants.feedback import (
    MAX_IMAGE_COUNT_FEEDBACK,
    MAX_IMAGE_SIZE_FEEDBACK,
)
from feedback.models import FeedbackForm, FeedbackImage
from feedback.services import feedback_image_upload_handler

User = get_user_model()


class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания обратной связи."""

    attachments = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = FeedbackForm
        fields = [
            'subject',
            'content',
            'attachments',
        ]

    def create(self, validated_data: dict) -> FeedbackForm:
        """Создание обратной связи."""
        attachments = validated_data.pop('attachments', [])
        user = self.context['request'].user
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
        return feedback

    def validate_attachments(self, value: List):
        """Валидация изображений прикреплённых к форме обратной связи:

        - Количество - не более 5.
        - Размер каждого изображения - не более 5 МБ.
        - Формат изображений - только JPEG/PNG.
        """
        if len(value) > MAX_IMAGE_COUNT_FEEDBACK:
            raise ValidationError(
                'Количество изображений не должно превышать 5 шт.')
        for image in value:
            if image.content_type.split('/')[1] not in ('jpeg', 'png'):
                raise ValidationError(
                    'Неподдерживаемый тип файла. Пожалуйста, загрузите файл '
                    'в формате png либо jpeg.')
            if image.size > MAX_IMAGE_SIZE_FEEDBACK:
                raise ValidationError(
                    'Размер изображения не должен превышать 5 МБ.')
        return value
