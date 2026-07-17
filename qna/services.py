import logging

from django.db.models import Model

from qna.selectors import count_likes, delete_like, get_or_create_like
from users.services import update_user_rating

logger = logging.getLogger(__name__)


def toggle_like(
    like_model: type[Model],
    target_obj: Model,
    user: Model,
    target_field: str,
) -> dict:
    """Универсальный toggle-лайк.

    Создаёт или удаляет лайк и возвращает статус с количеством лайков.
    Избегает дополнительного COUNT запроса, используя агрегацию из БД.

    Args:
        like_model: Модель лайка (QuestionLike или AnswerLike).
        target_obj: Объект, который лайкают (Question или Answer).
        user: Пользователь, который ставит лайк.
        target_field: Имя поля в like_model для связи с target_obj.

    Returns:
        dict: {'liked': bool, 'likes_count': int}.

    """
    like, created = get_or_create_like(
        like_model=like_model,
        target_field=target_field,
        target_obj=target_obj,
        user=user,
    )
    if not created:
        delete_like(like)
        liked = False
        delta = -1
    else:
        liked = True
        delta = 1

    # Обновляем рейтинг автора поста
    author = getattr(target_obj, 'user')

    logger.info(
        'Лайк %s: user_id=%s, target=%s, target_id=%s, author_id=%s',
        'создан' if liked else 'удалён',
        user.pk,
        target_field,
        target_obj.pk,
        author.pk,
    )
    if author.pk != user.pk:
        update_user_rating(user=author, delta=delta)
        logger.info(
            'Рейтинг автора обновлён: author_id=%s, delta=%d',
            author.pk,
            delta,
        )

    # Используем агрегацию из БД вместо .count() на prefetch-кеше,
    # чтобы избежать проблем с устаревшим кешем prefetch_related
    likes_count = count_likes(
        like_model=like_model,
        target_field=target_field,
        target_obj=target_obj,
    )

    return {
        'liked': liked,
        'likes_count': likes_count,
    }
