from django.db.models import Prefetch, QuerySet, Value
from django.db.models.functions import Concat

from feedback.models import Review
from users.models import Specialization


def get_reviews_queryset() -> QuerySet[Review]:
    """Возвращает оптимизированный queryset для отзывов.

    - select_related: user
    - prefetch_related: user__specializations
    - annotate: author_name (имя и фамилия пользователя)
    """
    return Review.objects.select_related('user').prefetch_related(
        Prefetch(
            'user__specializations',
            queryset=Specialization.objects.only('spec_id', 'name'),
        ),
    ).annotate(
        author_name=Concat(
            'user__first_name',
            Value(' '),
            'user__last_name',
        ),
    )


def create_review(user, text: str) -> Review:
    """Создаёт отзыв."""
    return Review.objects.create(user=user, text=text)