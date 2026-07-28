from django.db import transaction
from rest_framework import serializers

from qna.models import Answer
from qna.selectors import create_answer, create_answer_image
from qna.serializers.mixins import AuthorInfoMixin


class AnswerDetailSerializer(AuthorInfoMixin, serializers.ModelSerializer):
    """Сериализатор ответа для детальной страницы вопроса."""

    author_name = serializers.SerializerMethodField()
    author_rating = serializers.SerializerMethodField()
    author_avatar = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    is_owned_by_me = serializers.SerializerMethodField()
    is_liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = (
            'answer_id',
            'parent_answer_id',
            'content',
            'author_name',
            'author_rating',
            'author_avatar',
            'created_at',
            'likes_count',
            'images',
            'is_owned_by_me',
            'is_liked_by_me',
        )

    def get_author_name(self, obj: Answer) -> str:
        """Возвращает имя автора ответа."""
        return (
            f'{obj.user.first_name} {obj.user.last_name}'.strip()
            or obj.user.email
        )

    def get_author_rating(self, obj: Answer) -> int:
        """Возвращает рейтинг автора."""
        return obj.user.rating

    def get_author_avatar(self, obj: Answer) -> str:
        """Возвращает URL аватара автора."""
        return obj.user.avatar_url

    def get_images(self, obj: Answer) -> list[str]:
        """Возвращает список URL изображений."""
        return [img.image_url for img in obj.images.all()]

    def get_is_owned_by_me(self, obj: Answer) -> bool:
        """Проверяет, принадлежит ли ответ текущему пользователю.

        Используется фронтендом для отображения кнопок
        редактирования/удаления только для собственных ответов.
        """
        request = self.context.get('request')
        if request is None or not hasattr(request, 'user'):
            return False
        if request.user.is_anonymous:
            return False
        return obj.user == request.user

    def get_is_liked_by_me(self, obj: Answer) -> bool:
        """Проверяет, поставил ли текущий пользователь лайк этому ответу.

        Использует prefetch_related('likes') для избежания дополнительных
        запросов к БД. Аналогично is_owned_by_me, но проверяет наличие лайка
        через закешированное отношение likes.
        """
        request = self.context.get('request')
        if request is None or not hasattr(request, 'user'):
            return False
        if request.user.is_anonymous:
            return False
        return any(like.user_id == request.user.pk for like in obj.likes.all())


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
        fields = ('content', 'parent_answer', 'images')

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
        fields = ('answer_id',)
