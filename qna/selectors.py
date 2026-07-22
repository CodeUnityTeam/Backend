from typing import Any
from uuid import UUID

from django.db.models import Case, Count, Prefetch, Q, QuerySet, Value, When
from django.db.models.base import Model
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404

from qna.models import Answer, AnswerImage, Question, QuestionImage
from users.models import Skill


def get_question_or_404(question_id: UUID) -> Question:
    """Получает вопрос по ID или выбрасывает 404."""
    return get_object_or_404(Question, pk=question_id)


def get_answer_or_404(answer_id: UUID) -> Answer:
    """Получает ответ по ID или выбрасывает 404."""
    return get_object_or_404(Answer, pk=answer_id)


def get_question_detail_queryset() -> QuerySet[Question]:
    """Возвращает оптимизированный queryset для детальной страницы вопроса.

    - select_related: user
    - prefetch_related: answers, likes, images
    - annotate: likes_count, answers_count, author_name
    """
    return Question.objects.select_related('user').prefetch_related(
        Prefetch(
            'answers',
            queryset=Answer.objects.select_related(
                'user',
            ).prefetch_related('images').filter(is_active=True),
        ),
        'likes',
        'images',
    ).annotate(
        likes_count=Count('likes', distinct=True),
        answers_count=Count(
            'answers',
            filter=Q(answers__is_active=True),
        ),
        author_name=Case(
            When(
                is_anonymous=True,
                then=Value('Аноним'),
            ),
            default=Concat(
                'user__first_name',
                Value(' '),
                'user__last_name',
            ),
        ),
    )


def get_light_question_queryset() -> QuerySet[Question]:
    """Возвращает лёгкий queryset вопроса только с PK.

    Используется для actions, где не нужны prefetch (add_answer, like).
    """
    return Question.objects.only('pk')


def get_answer_detail_queryset() -> QuerySet[Answer]:
    """Возвращает оптимизированный queryset для ответов.

    - select_related: user, question
    - prefetch_related: likes, images
    """
    return Answer.objects.select_related(
        'user', 'question',
    ).prefetch_related('likes', 'images')


def get_all_skills() -> QuerySet[Skill]:
    """Возвращает все навыки."""
    return Skill.objects.all()


def create_question(
    user: Model,
    **validated_data: Any,
) -> Question:
    """Создаёт вопрос."""
    return Question.objects.create(user=user, **validated_data)


def set_question_skills(question: Question, tags: list) -> None:
    """Устанавливает навыки для вопроса."""
    question.skills.set(tags)


def create_question_image(
    question: Question,
    uploaded_by: Model,
    **image_data: Any,
) -> QuestionImage:
    """Создаёт изображение для вопроса."""
    return QuestionImage.objects.create(
        question=question,
        uploaded_by=uploaded_by,
        **image_data,
    )


def get_question_images(question: Question) -> QuerySet[QuestionImage]:
    """Возвращает все изображения вопроса."""
    return question.images.all()


def get_question_images_excluding(
    question: Question,
    exclude_ids: set,
) -> QuerySet[QuestionImage]:
    """Возвращает изображения вопроса, исключая указанные ID."""
    return question.images.exclude(image_id__in=exclude_ids)


def update_question_image(
    image: QuestionImage,
    **fields: Any,
) -> None:
    """Обновляет поля изображения вопроса."""
    image.save(update_fields=list(fields.keys()))


def delete_question_image(image: QuestionImage) -> None:
    """Удаляет изображение вопроса."""
    image.delete()


def create_answer(
    user: Model,
    question: Question,
    **validated_data: Any,
) -> Answer:
    """Создаёт ответ."""
    return Answer.objects.create(
        user=user,
        question=question,
        **validated_data,
    )


def create_answer_image(
    answer: Answer,
    uploaded_by: Model,
    **image_data: Any,
) -> AnswerImage:
    """Создаёт изображение для ответа."""
    return AnswerImage.objects.create(
        answer=answer,
        uploaded_by=uploaded_by,
        **image_data,
    )


def get_or_create_like(
    like_model: type[Model],
    target_field: str,
    target_obj: Model,
    user: Model,
) -> tuple:
    """Создаёт или получает существующий лайк."""
    return like_model.objects.get_or_create(
        **{target_field: target_obj, 'user': user},
    )


def delete_like(like: Model) -> None:
    """Удаляет лайк."""
    like.delete()


def count_likes(
    like_model: type[Model],
    target_field: str,
    target_obj: Model,
) -> int:
    """Считает количество лайков для объекта."""
    return like_model.objects.filter(
        **{target_field: target_obj},
    ).count()
