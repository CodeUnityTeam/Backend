from rest_framework import serializers

from qna.models import Answer, AnswerImage, Question, QuestionImage
from users.models import Skill


class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов(скиллов)."""

    id = serializers.UUIDField(source='skill_id')

    class Meta:
        model = Skill
        fields = ['id', 'name']


class LikeSerializer(serializers.Serializer):
    """Сериализатор лайков."""

    liked = serializers.BooleanField()
    likes_count = serializers.IntegerField()


class AnswerDetailSerializer(serializers.ModelSerializer):
    """Сериализатор ответа для детальной страницы вопроса."""

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

    def create(self, validated_data: dict) -> Answer:
        """Создаёт ответ с изображениями."""
        images = validated_data.pop('images', [])
        user = self.context['request'].user
        question = self.context['question']

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


class QuestionImageMetaSerializer(serializers.Serializer):
    """Метаданные изображения при создании вопроса."""

    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания вопроса."""

    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        source='skills',
        queryset=Skill.objects.all(),
        label='Навыки',
    )
    images = QuestionImageMetaSerializer(
        many=True,
        required=False,
        write_only=True,
        label='Изображения',
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
        """Создаёт вопрос с тегами и изображениями."""
        tags = validated_data.pop('skills', [])
        images = validated_data.pop('images', [])
        user = self.context['request'].user

        question = Question.objects.create(user=user, **validated_data)
        question.skills.set(tags)

        for image in images:
            QuestionImage.objects.create(
                question=question,
                uploaded_by=user,
                image_url=image['image_url'],
                original_name=image['original_name'],
                file_size=image['file_size'],
                mime_type=image['mime_type'],
            )

        return question


class AnswerCreateResponseSerializer(serializers.ModelSerializer):
    """Сериализатор ответа на создание ответа."""

    class Meta:
        model = Answer
        fields = ['answer_id']


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
    likes_count = serializers.SerializerMethodField()
    answers_count = serializers.SerializerMethodField()

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
        """Возвращает имя автора или Аноним."""
        if obj.is_anonymous:
            return 'Аноним'
        return f'{obj.user.first_name} {obj.user.last_name}'.strip()

    def get_likes_count(self, obj: Question) -> int:
        """Возвращает количество лайков."""
        return obj.likes.count()

    def get_answers_count(self, obj: Question) -> int:
        """Возвращает количество активных ответов."""
        return obj.answers.filter(is_active=True).count()


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Сериализатор детальной страницы вопроса."""

    tags = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='skills',
    )
    author_name = serializers.CharField(
        source='user.get_full_name',
        read_only=True,
    )
    likes_count = serializers.SerializerMethodField()
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

    def get_likes_count(self, obj: Question) -> int:
        """Возвращает количество лайков."""
        return obj.likes.count()

    def get_images(self, obj: Question) -> list[str]:
        """Возвращает список URL изображений."""
        return list(obj.images.values_list('image_url', flat=True))


class FileUploadSerializer(serializers.Serializer):
    """Сериализатор для валидации загружаемого файла."""

    file: serializers.ImageField = serializers.ImageField(write_only=True)


class FileUploadResponseSerializer(serializers.Serializer):
    """Сериализатор ответа на загрузку файла."""

    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()
