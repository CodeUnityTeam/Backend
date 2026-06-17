from django.db import transaction
from rest_framework import serializers

from qna.models import Answer
from qna.selectors import create_answer, create_answer_image


class AnswerDetailSerializer(serializers.ModelSerializer):
    """Сериализатор ответа для детальной страницы вопроса."""

    author_name = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Answer
        fields = [
            'answer_id',
            'parent_answer_id',
            'content',
            'author_name',
            'created_at',
            'likes_count',
            'images',
        ]

    def get_author_name(self, obj: Answer) -> str:
        """Возвращает имя автора ответа."""
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.email

    def get_images(self, obj: Answer) -> list[str]:
        """Возвращает список URL изображений."""
        return [img.image_url for img in obj.images.all()]


class AnswerImageMetaSerializer(serializers.Serializer):
    """Метаданные изображения при создании ответа."""

    image_id = serializers.UUIDField(required=False)
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()


class AnswerCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания ответа."""

    images = AnswerImageMetaSerializer(
        many=True,
        required=False,
        write_only=True,
        label='Изображения',
    )

    class Meta:
        model = Answer
        fields = ['content', 'parent_answer', 'images']

    def validate_parent_answer(self, value: Answer | None) -> Answer | None:
        """Проверяет, что parent_answer относится к тому же вопросу."""
        if value is None:
            return value
        question = self.context.get('question')
        if question and value.question_id != question.pk:
            raise serializers.ValidationError(
                'Родительский ответ должен относиться к тому же вопросу.',
            )
        return value

    def create(self, validated_data: dict) -> Answer:
        """Создаёт ответ с изображениями."""
        images = validated_data.pop('images', [])
        user = self.context['request'].user
        question = self.context['question']

        with transaction.atomic():
            answer = create_answer(
                user=user,
                question=question,
                **validated_data,
            )

            for image in images:
                create_answer_image(
                    answer=answer,
                    uploaded_by=user,
                    image_url=image['image_url'],
                    original_name=image['original_name'],
                    file_size=image['file_size'],
                    mime_type=image['mime_type'],
                )

        return answer


class AnswerCreateResponseSerializer(serializers.ModelSerializer):
    """Сериализатор ответа на создание ответа."""

    class Meta:
        model = Answer
        fields = ['answer_id']
