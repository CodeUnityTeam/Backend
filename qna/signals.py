import logging
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver

from core.constants.cache import CACHE_KEY_QNA_PREFIX
from feedback.models import FeedbackImage
from minio.s3_utils import MediaType, S3Service
from qna.models import (
    Answer,
    AnswerImage,
    AnswerLike,
    Question,
    QuestionImage,
    QuestionLike,
)
from users.models import User
from users.services import update_user_rating

logger = logging.getLogger(__name__)


def _invalidate_question(question_id: Any, invalidate_list: bool) -> None:
    """Очистить кэш вопроса после успешного коммита БД."""
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:{question_id}:*',
    )
    if invalidate_list:
        cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:list:ids:*')


@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
def invalidate_question_cache(
    sender: Any,
    instance: Question,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию изменённого вопроса."""
    question_id = instance.pk
    transaction.on_commit(
        lambda question_id=question_id: _invalidate_question(
            question_id,
            invalidate_list=True,
        ),
    )
    logger.info(
        'Инвалидация вопроса запланирована: question_id=%s',
        question_id,
    )


@receiver(post_save, sender=Answer)
@receiver(post_delete, sender=Answer)
def invalidate_answer_cache(
    sender: Any,
    instance: Answer,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш вопроса при добавлении/удалении ответа.

    Очищает детали вопроса и список вопросов, т.к. answers_count
    отображается в QuestionListSerializer.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:{instance.question_id}:*',
    )
    cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:list:*')
    logger.info(
        'Инвалидация ответа запланирована: answer_id=%s, question_id=%s',
        instance.pk,
        instance.question_id,
    )


@receiver(m2m_changed, sender=Question.skills.through)
def invalidate_question_skills_cache(
    sender: Any,
    instance: Any,
    action: str,
    **kwargs: Any,
) -> None:
    """Инвалидировать вопрос после изменения его навыков."""
    if kwargs.get('reverse', False):
        if action in {'post_add', 'post_remove'}:
            question_ids = tuple(kwargs.get('pk_set') or ())
        elif action == 'pre_clear':
            question_ids = tuple(
                instance.questions.values_list('question_id', flat=True),
            )
        else:
            return
    elif action in {'post_add', 'post_remove', 'pre_clear'}:
        question_ids = (instance.question_id,)
    else:
        return

    for question_id in question_ids:
        transaction.on_commit(
            lambda question_id=question_id: _invalidate_question(
                question_id,
                invalidate_list=True,
            ),
        )


@receiver(post_save, sender=QuestionImage)
@receiver(post_delete, sender=QuestionImage)
def invalidate_question_image_cache(
    sender: Any,
    instance: QuestionImage,
    **kwargs: Any,
) -> None:
    """Инвалидировать detail вопроса после изменения изображения."""
    question_id = instance.question_id
    transaction.on_commit(
        lambda question_id=question_id: _invalidate_question(
            question_id,
            invalidate_list=False,
        ),
    )


@receiver(post_save, sender=AnswerImage)
@receiver(post_delete, sender=AnswerImage)
def invalidate_answer_image_cache(
    sender: Any,
    instance: AnswerImage,
    **kwargs: Any,
) -> None:
    """Инвалидировать detail вопроса после изменения изображения ответа."""
    question_id = instance.answer.question_id
    transaction.on_commit(
        lambda question_id=question_id: _invalidate_question(
            question_id,
            invalidate_list=False,
        ),
    )


@receiver(post_save, sender=QuestionLike)
@receiver(post_delete, sender=QuestionLike)
def invalidate_question_like_cache(
    sender: Any,
    instance: QuestionLike,
    **kwargs: Any,
) -> None:
    """Инвалидирует кэш при лайке/снятии лайка вопроса.

    Очищает детали только для пользователя, поставившего лайк.
    Также очищает список вопросов, т.к. likes_count отображается
    в QuestionListSerializer и должен быть актуальным.
    """
    cache.delete_pattern(
        f'{CACHE_KEY_QNA_PREFIX}:detail:'
        f'{instance.question_id}:{instance.user_id}',
    )
    cache.delete_pattern(f'{CACHE_KEY_QNA_PREFIX}:list:*')


@receiver(post_save, sender=AnswerLike)
@receiver(post_delete, sender=AnswerLike)
def invalidate_answer_like_cache(
    sender: Any,
    instance: AnswerLike,
    **kwargs: Any,
) -> None:
    """Запланировать инвалидацию detail после изменения лайка ответа."""
    question_id = instance.answer.question_id
    transaction.on_commit(
        lambda question_id=question_id: _invalidate_question(
            question_id,
            invalidate_list=False,
        ),
    )


@receiver(pre_delete, sender=Question)
@receiver(pre_delete, sender=Answer)
def change_author_rating_on_delete(
    sender: Any,
    instance: Question | Answer,
    **kwargs: Any,
) -> None:
    """Вычитает лайки из рейтинга автора при удалении вопроса/ответа."""
    likes_count = instance.likes.count()
    if likes_count:
        update_user_rating(user=instance.user, delta=-likes_count)
        logger.info(
            'Рейтинг автора уменьшен при удалении: '
            'author_id=%s, delta=%d, type=%s',
            instance.user.pk,
            -likes_count,
            'question' if isinstance(instance, Question) else 'answer',
        )


@receiver(pre_save, sender=Question)
@receiver(pre_save, sender=Answer)
def change_author_rating_on_save(
    sender: Any,
    instance: Question | Answer,
    **kwargs: Any,
) -> None:
    """Вычитает лайки из рейтинга автора при деактивации вопроса/ответа."""
    if not instance.pk:
        return
    try:
        post = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if post.is_active:
        return
    likes_count = instance.likes.count()
    if likes_count:
        update_user_rating(user=instance.user, delta=-likes_count)
        logger.info(
            'Рейтинг автора уменьшен при деактивации: '
            'author_id=%s, delta=%d, type=%s',
            instance.user.pk,
            -likes_count,
            'question' if isinstance(instance, Question) else 'answer',
        )


@receiver(pre_delete, sender=Question)
def delete_question_images_from_minio(
    sender: type,
    instance: Question,
    **kwargs: object,
) -> None:
    """Удаляет файлы из MinIO при каскадном удалении вопроса.

    Django при удалении Question с CASCADE удаляет связанные QuestionImage,
    но post_delete для QuestionImage может не сработать, т.к. Django
    удаляет related objects напрямую через QuerySet.delete(), минуя
    индивидуальные delete() каждого экземпляра.

    Поэтому собираем URL изображений ДО удаления и планируем удаление
    файлов после коммита транзакции.
    """
    image_urls: list[str] = list(
        instance.images.values_list('image_url', flat=True),
    )
    if image_urls:
        logger.info(
            'Удаление изображений вопроса из MinIO: question_id=%s',
            instance.pk,
        )
        transaction.on_commit(
            lambda urls=image_urls: [
                S3Service.delete(MediaType.QUESTION_IMAGE, url)
                for url in urls
            ],
        )


@receiver(pre_delete, sender=Answer)
def delete_answer_images_from_minio(
    sender: type,
    instance: Answer,
    **kwargs: object,
) -> None:
    """Удаляет файлы из MinIO при каскадном удалении ответа.

    Аналогично delete_question_images_from_minio — собираем URL
    изображений ДО удаления ответа.
    """
    image_urls: list[str] = list(
        instance.images.values_list('image_url', flat=True),
    )
    if image_urls:
        logger.info(
            'Удаление изображений ответа из MinIO: answer_id=%s',
            instance.pk,
        )
        transaction.on_commit(
            lambda urls=image_urls: [
                S3Service.delete(MediaType.ANSWER_IMAGE, url)
                for url in urls
            ],
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
        logger.info(
            'Удаление изображения вопроса из MinIO: image_id=%s, url=%s',
            instance.pk,
            image_url,
        )
        transaction.on_commit(
            lambda url=image_url: S3Service.delete(
                MediaType.QUESTION_IMAGE, url,
            ),
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
        logger.info(
            'Удаление изображения ответа из MinIO: image_id=%s, '
            'answer_id=%s, url=%s',
            instance.pk,
            instance.answer_id,
            image_url,
        )
        transaction.on_commit(
            lambda url=image_url: S3Service.delete(
                MediaType.ANSWER_IMAGE, url,
            ),
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
        logger.info(
            'Удаление изображения обратной связи из MinIO: image_id=%s, '
            'feedback_id=%s, url=%s',
            instance.pk,
            instance.feedback_id,
            image_url,
        )
        transaction.on_commit(
            lambda url=image_url: S3Service.delete(
                MediaType.FEEDBACK_IMAGE, url,
            ),
        )


@receiver(post_delete, sender=User)
def delete_avatar_from_minio(
    sender: type,
    instance: User,
    **kwargs: object,
) -> None:
    """Удаляет файл из MinIO при удалении avatar_url."""
    if instance.avatar_url:
        avatar_url: str = instance.avatar_url
        logger.info(
            'Удаление аватара из MinIO: user_id=%s, url=%s',
            instance.pk,
            avatar_url,
        )
        transaction.on_commit(
            lambda url=avatar_url: S3Service.delete(
                MediaType.AVATAR, url,
            ),
        )
