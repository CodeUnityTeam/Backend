from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from feedback.models import FeedbackImage
from qna.models import AnswerImage, QuestionImage
from qna.services import image_minio_client
from users.models import User
from users.services import avatar_minio_client


# TODO [QNA-18/19]: Проблема с lambda внутри on_commit (аналогично users/services.py:39).
#   При множественном удалении QuestionImage/AnswerImage все lambda внутри
#   on_commit будут использовать последнее значение image_url из цикла,
#   т.к. lambda захватывает переменную по ссылке, а не по значению.
#   Решение: использовать лямбду с дефолтным аргументом:
#     transaction.on_commit(lambda url=image_url: image_minio_client.delete_file(url))
#   Или вынести в отдельную функцию.

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
            lambda: image_minio_client.delete_file(image_url),
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
            lambda: image_minio_client.delete_file(image_url),
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
            lambda: image_minio_client.delete_file(image_url),
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
