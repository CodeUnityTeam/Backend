from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.constants.cache import CACHE_KEY_QNA_PREFIX
from feedback.models import FeedbackImage
from qna.models import (
    Answer,
    AnswerImage,
    AnswerLike,
    Question,
    QuestionImage,
    QuestionLike,
)
from qna.services import image_minio_client
from users.models import User
from users.services import avatar_minio_client


@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
def invalidate_question_cache(
    sender: Any,
    instance: Question,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при создании/изменении/удалении вопроса."""
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:{instance.pk}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:list:*')


@receiver(post_save, sender=Answer)
@receiver(post_delete, sender=Answer)
def invalidate_answer_cache(
    sender: Any,
    instance: Answer,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш вопроса при добавлении/удалении ответа."""
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:{instance.question_id}:*',
    )


@receiver(post_save, sender=QuestionLike)
@receiver(post_delete, sender=QuestionLike)
def invalidate_question_like_cache(
    sender: Any,
    instance: QuestionLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при лайке/снятии лайка вопроса.

    Очищает только детальную страницу вопроса для конкретного пользователя.
    Список вопросов не очищается.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:'
        f'{instance.question_id}:{instance.user_id}',
    )


@receiver(post_save, sender=AnswerLike)
@receiver(post_delete, sender=AnswerLike)
def invalidate_answer_like_cache(
    sender: Any,
    instance: AnswerLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш вопроса при лайке/снятии лайка ответа.

    Очищает детали вопроса только для пользователя, поставившего лайк.
    Список вопросов не очищается — лайк ответа не влияет на список.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:'
        f'{instance.answer.question_id}:{instance.user_id}',
    )


@receiver(post_delete, sender=QuestionImage)
def delete_question_image_from_minio(
    sender: type,
    instance: QuestionImage,
    **kwargs: object,
) -> None:
    """Удаляет файл из MinIO при удалении QuestionImage."""
    if instance.image_url:
        image_url: str = instance.image_url
        transaction.on_commit(
            lambda url=image_url: image_minio_client.delete_file(url),
        )


@receiver(post_delete, sender=AnswerImage)
def delete_answer_image_from_minio(
    sender: type,
    instance: AnswerImage,
    **kwargs: object,
) -> None:
    """Удаляет файл из MinIO при удалении AnswerImage."""
    if instance.image_url:
        image_url: str = instance.image_url
        transaction.on_commit(
            lambda url=image_url: image_minio_client.delete_file(url),
        )


@receiver(post_delete, sender=FeedbackImage)
def delete_feedback_image_from_minio(
    sender: type,
    instance: FeedbackImage,
    **kwargs: object,
) -> None:
    """Удаляет файл из MinIO при удалении FeedbackImage."""
    if instance.image_url:
        image_url: str = instance.image_url
        transaction.on_commit(
            lambda url=image_url: image_minio_client.delete_file(url),
        )


@receiver(post_delete, sender=User)
def delete_avatar_from_minio(
    sender: type,
    instance: User,
    **kwargs: object,
) -> None:
    """Удаляет файл из MinIO при удалении avatar_url."""
    if instance.avatar_url:
        avatar_minio_client.delete_file(instance.avatar_url)
