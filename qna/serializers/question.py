from django.db import transaction
from django.db.models import QuerySet
from rest_framework import serializers

from core.constants.qna import (
    MAX_TITLE_QUESTION,
    MIN_DESC_QUESTION,
    MIN_TITLE_QUESTION,
)
from qna.models import Question, QuestionImage
from qna.serializers.answer import AnswerDetailSerializer
from users.models import Skill


class LazySkillField(serializers.PrimaryKeyRelatedField):
    """Поле с ленивой загрузкой queryset для Skill.

    Используется при создании вопроса.
    """

    def get_queryset(self) -> QuerySet[Skill]:
        """Возвращает queryset с ленивой загрузкой."""
        return Skill.objects.all()


class QuestionImageMetaSerializer(serializers.Serializer):
    """Метаданные изображения при создании вопроса."""

    image_id = serializers.UUIDField(required=False)
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания вопроса."""

    tags = LazySkillField(
        many=True,
        source='skills',
        label='Навыки',
    )
    images = QuestionImageMetaSerializer(
        many=True,
        required=False,
        write_only=True,
        label='Изображения',
    )
    title = serializers.CharField(
        min_length=MIN_TITLE_QUESTION,
        max_length=MAX_TITLE_QUESTION,
    )
    description = serializers.CharField(
        min_length=MIN_DESC_QUESTION,
    )

    class Meta:
        model = Question
        fields = [
            'title',
            'description',
            'tags',
            'is_anonymous',
            'images',
        ]

    def create(self, validated_data: dict) -> Question:
        """Создание вопроса."""
        tags = validated_data.pop('skills', [])
        images = validated_data.pop('images', [])
        user = self.context['request'].user

        with transaction.atomic():
            question = Question.objects.create(user=user, **validated_data)
            question.skills.set(tags)

            for image in images:
                QuestionImage.objects.create(
                    question=question,
                    uploaded_by=user,
                    image_id=image['image_id'],
                    image_url=image['image_url'],
                    original_name=image['original_name'],
                    file_size=image['file_size'],
                    mime_type=image['mime_type'],
                )

        return question


class QuestionUpdateSerializer(QuestionCreateSerializer):
    """Сериализатор обновления вопроса."""

    class Meta:
        model = Question
        fields = [
            'title',
            'description',
            'tags',
            'is_anonymous',
            'images',
        ]

    def update(self, instance: Question, validated_data: dict) -> Question:
        """Обновление вопроса."""
        tags = validated_data.pop('skills', None)
        images = validated_data.pop('images', None)

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            if tags is not None:
                instance.skills.set(tags)

            if images is not None:
                existing_images = {
                    str(image.image_id): image
                    for image in instance.images.all()
                }
                incoming_ids: set[str] = set()
                user = self.context['request'].user

                for image_data in images:
                    image_id = image_data.get('image_id')

                    if image_id and str(image_id) in existing_images:
                        image_obj = existing_images[str(image_id)]
                        incoming_ids.add(str(image_id))

                        image_obj.image_url = image_data['image_url']
                        image_obj.original_name = image_data['original_name']
                        image_obj.file_size = image_data['file_size']
                        image_obj.mime_type = image_data['mime_type']
                        image_obj.save(
                            update_fields=[
                                'image_url',
                                'original_name',
                                'file_size',
                                'mime_type',
                            ],
                        )
                    else:
                        new_image = QuestionImage.objects.create(
                            question=instance,
                            uploaded_by=user,
                            image_url=image_data['image_url'],
                            original_name=image_data['original_name'],
                            file_size=image_data['file_size'],
                            mime_type=image_data['mime_type'],
                        )
                        incoming_ids.add(str(new_image.image_id))

                for image in instance.images.exclude(
                    image_id__in=incoming_ids,
                ):
                    image.delete()

        return instance


class QuestionCreateResponseSerializer(serializers.ModelSerializer):
    """Сериализатор ответа на создание вопроса."""

    class Meta:
        model = Question
        fields = ['question_id']


class QuestionListSerializer(serializers.ModelSerializer):
    """Сериализатор вопроса для списка."""

    tags = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='skills',
    )
    author_name = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    answers_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Question
        fields = [
            'question_id',
            'title',
            'description',
            'tags',
            'author_name',
            'created_at',
            'likes_count',
            'answers_count',
        ]

    def get_author_name(self, obj: Question) -> str:
        """Возвращает имя автора или 'Аноним'."""
        if obj.is_anonymous:
            return 'Аноним'
        return (
            f'{obj.user.first_name} {obj.user.last_name}'.strip() or
            obj.user.email
        )


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Сериализатор детальной страницы вопроса."""

    tags = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='skills',
    )
    author_name = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    images = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'question_id',
            'title',
            'description',
            'tags',
            'author_name',
            'created_at',
            'likes_count',
            'images',
        ]

    def get_author_name(self, obj: Question) -> str:
        """Возвращает имя автора или 'Аноним'."""
        if obj.is_anonymous:
            return 'Аноним'
        return (
            f'{obj.user.first_name} {obj.user.last_name}'.strip() or
            obj.user.email
        )

    def get_images(self, obj: Question) -> list[str]:
        """Возвращает список URL изображений."""
        return [img.image_url for img in obj.images.all()]


class QuestionWithAnswersSerializer(QuestionDetailSerializer):
    """Объединяет вопрос и ответы в один ответ.

    Наследует все поля от QuestionDetailSerializer и добавляет ответы.
    """

    answers = AnswerDetailSerializer(many=True, read_only=True)

    class Meta(QuestionDetailSerializer.Meta):
        fields = QuestionDetailSerializer.Meta.fields + ['answers']
