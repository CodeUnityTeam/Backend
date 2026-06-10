from django.db import transaction
from rest_framework import serializers

from qna.models import Question, QuestionImage
from users.models import Skill


class QuestionImageMetaSerializer(serializers.Serializer):
    """Метаданные изображения при создании вопроса."""

    image_id = serializers.UUIDField(required=False)
    image_url = serializers.URLField()
    original_name = serializers.CharField()
    file_size = serializers.IntegerField()
    mime_type = serializers.CharField()


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания вопроса."""

    # TODO [QNA-5/19]: PrimaryKeyRelatedField с Skill.objects.all() загружает все скиллы.
    #   На строке 21: queryset=Skill.objects.all() — это выполняется при импорте
    #   модуля, а не при каждом запросе. Но если скиллы добавляются в БД после
    #   импорта, они не будут доступны для валидации до перезапуска.
    #   Решение: использовать queryset=Skill.objects.all() в __init__ или
    #   переопределить field с lazy-загрузкой.
    # TODO [QNA-6/19]: Отсутствует валидация title и description.
    #   В модели Question.title (models.py:37) нет MinLengthValidator.
    #   В сериализаторе тоже нет проверки минимальной длины заголовка.
    #   Пустой заголовок или заголовок из 1 символа пройдёт валидацию.
    # TODO [QNA-7/19]: QuestionCreateSerializer используется и для create, и для update.
    #   Метод update (строка 66) содержит сложную логику синхронизации
    #   изображений. При этом для update используется тот же сериализатор,
    #   что и для create. Лучше разделить на отдельные сериализаторы.

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
                    image_url=image['image_url'],
                    original_name=image['original_name'],
                    file_size=image['file_size'],
                    mime_type=image['mime_type'],
                )

        return question

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


# TODO [QNA-8/19]: Заменить SerializerMethodField на аннотированные поля.
#   Проблема: QuestionListSerializer использует SerializerMethodField для
#   likes_count и answers_count, что вызывает N+1 запросов:
#     1. get_likes_count: obj.likes.count() — отдельный запрос на вопрос.
#     2. get_answers_count: obj.answers.filter(is_active=True).count() —
#        ещё один запрос на вопрос.
#   Аналогичная проблема в QuestionDetailSerializer.
#
#   Решение через стандартный DRF + аннотации:
#   1. В QuestionViewSet.queryset добавить аннотации:
#      from django.db.models import Count, Q
#
#      class QuestionViewSet(ModelViewSet):
#          queryset = Question.objects.select_related('user').annotate(
#              likes_count=Count('likes', distinct=True),
#              answers_count=Count(
#                  'answers',
#                  filter=Q(answers__is_active=True),
#                  distinct=True,
#              ),
#          ).prefetch_related('skills', 'images')
#
#   2. В QuestionListSerializer заменить SerializerMethodField на IntegerField:
#      class QuestionListSerializer(serializers.ModelSerializer):
#          tags = serializers.SlugRelatedField(
#              many=True, read_only=True,
#              slug_field='name', source='skills',
#          )
#          author_name = serializers.SerializerMethodField()
#          likes_count = serializers.IntegerField(read_only=True)
#          answers_count = serializers.IntegerField(read_only=True)
#
#          class Meta:
#              model = Question
#              fields = [
#                  'question_id', 'title', 'description',
#                  'tags', 'author_name', 'created_at',
#                  'likes_count', 'answers_count',
#              ]
#
#          def get_author_name(self, obj):
#              if obj.is_anonymous:
#                  return 'Аноним'
#              return f'{obj.user.first_name} {obj.user.last_name}'.strip()
#
#   3. В QuestionDetailSerializer то же самое:
#      class QuestionDetailSerializer(serializers.ModelSerializer):
#          tags = serializers.SlugRelatedField(
#              many=True, read_only=True,
#              slug_field='name', source='skills',
#          )
#          author_name = serializers.CharField(
#              source='user.get_full_name', read_only=True,
#          )
#          likes_count = serializers.IntegerField(read_only=True)
#          images = serializers.SerializerMethodField()
#
#          class Meta:
#              model = Question
#              fields = [
#                  'question_id', 'title', 'description',
#                  'tags', 'author_name', 'created_at',
#                  'likes_count', 'images',
#              ]
#
#          def get_images(self, obj):
#              return list(obj.images.values_list('image_url', flat=True))
#
#   Преимущества:
#     - Аннотации выполняются на уровне БД — один запрос вместо N+1.
#     - IntegerField(read_only=True) вместо SerializerMethodField — меньше кода.
#     - Аннотированные поля доступны для фильтрации и сортировки.
#     - distinct=True предотвращает задвоение при JOIN-ах.
#     - select_related('user') — нет N+1 на author_name.
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


# TODO [QNA-9/19]: Заменить SerializerMethodField на аннотированные поля.
#   Проблема: QuestionDetailSerializer.get_likes_count (строка 244) делает
#   obj.likes.count() — отдельный запрос для каждого вопроса.
#   Аналогично QuestionListSerializer.
#
#   Решение: см. TODO в QuestionListSerializer выше.
#   После добавления аннотации likes_count=Count('likes') в queryset
#   QuestionViewSet, заменить:
#     likes_count = serializers.SerializerMethodField()
#     def get_likes_count(self, obj): return obj.likes.count()
#   на:
#     likes_count = serializers.IntegerField(read_only=True)
#
#   Дополнительно:
#   - Учесть is_anonymous в author_name (как в QuestionListSerializer):
#     author_name = serializers.SerializerMethodField()
#     def get_author_name(self, obj):
#         if obj.is_anonymous:
#             return 'Аноним'
#         return obj.user.get_full_name()
#
#   - Для images использовать nested сериализатор вместо values_list:
#     class QuestionImageSerializer(serializers.ModelSerializer):
#         class Meta:
#             model = QuestionImage
#             fields = ['image_id', 'image_url', 'original_name']
#
#     images = QuestionImageSerializer(many=True, read_only=True)
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
