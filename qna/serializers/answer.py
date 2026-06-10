from django.db import transaction
from rest_framework import serializers

from qna.models import Answer, AnswerImage


class AnswerDetailSerializer(serializers.ModelSerializer):
    """Сериализатор ответа для детальной страницы вопроса."""

    # TODO [QNA-10/19]: N+1 запрос в AnswerDetailSerializer.get_images.
    #   obj.images.values_list('image_url', flat=True) — отдельный запрос
    #   для каждого ответа. При загрузке страницы вопроса с 20 ответами
    #   будет 20 дополнительных запросов.
    #   Решение: добавить prefetch_related('images') в queryset
    #   QuestionViewSet.retrieve или в отдельный селектор.
    # TODO [QNA-11/19]: AnswerDetailSerializer использует likes_count из модели,
    #   но это поле не синхронизируется (см. models.py:117).
    #   Фактически всегда будет 0.

    author_name = serializers.CharField(
        source='user.get_full_name',
        read_only=True,
    )
    images = serializers.SerializerMethodField()

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

    def get_images(self, obj: Answer) -> list[str]:
        """Возвращает список URL изображений."""
        return list(obj.images.values_list('image_url', flat=True))


class AnswerImageMetaSerializer(serializers.Serializer):
    """Метаданные изображения при создании ответа."""

    image_id = serializers.UUIDField(required=False)
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()


class AnswerCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания ответа."""

    # TODO [QNA-12/19]: Отсутствует валидация parent_answer.
    #   Поле parent_answer (ForeignKey на Answer) может быть указано,
    #   но нет проверки, что parent_answer принадлежит тому же вопросу.
    #   Можно создать ответ- reply на ответ из другого вопроса.
    #   Решение: добавить validate_parent_answer или validate:
    #   if parent_answer and parent_answer.question_id != question.pk:
    #       raise ValidationError('Родительский ответ из другого вопроса')

    images = AnswerImageMetaSerializer(
        many=True,
        required=False,
        write_only=True,
        label='Изображения',
    )

    class Meta:
        model = Answer
        fields = ['content', 'parent_answer', 'images']

    def create(self, validated_data: dict) -> Answer:
        """Создаёт ответ с изображениями."""
        images = validated_data.pop('images', [])
        user = self.context['request'].user
        question = self.context['question']

        with transaction.atomic():
            answer = Answer.objects.create(
                user=user,
                question=question,
                **validated_data,
            )

            for image in images:
                AnswerImage.objects.create(
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
