from typing import Optional

import django_filters
from django.db.models import Count, Q, QuerySet
from rest_framework.exceptions import PermissionDenied

from core.filters import UUIDInFilter

from .models import Question


class QuestionFilter(django_filters.FilterSet):
    """Фильтр вопросов."""

    tags = UUIDInFilter(
        field_name='skills__skill_id',
        label='Теги (по ID навыков)',
    )
    filter = django_filters.CharFilter(
        method='filter_by_type', label='Тип фильтра',
    )
    search = django_filters.CharFilter(
        method='filter_search',
        label='Поиск по заголовку и описанию',
    )

    class Meta:
        model = Question
        fields = ()

    def filter_by_type(
        self,
        queryset: QuerySet[Question],
        name: str,
        value: str | None,
    ) -> QuerySet[Question]:
        """Фильтрация вопросов по типу.

        Args:
            queryset: Исходный набор запросов модели Question.
            name: Имя поля фильтра (всегда 'filter').
            value: Значение параметра (popular, no_answers, my).

        Returns:
            Отфильтрованный и отсортированный QuerySet.

        """
        if value == 'popular':
            # Сортировка по количеству лайков (по убыванию)
            return queryset.annotate(
                likes_count=Count('likes'),
            ).order_by('-likes_count')
        if value == 'no_answers':
            # Вопросы без ответов
            return queryset.annotate(
                answers_count=Count('answers'),
            ).filter(answers_count=0)
        if value == 'my':
            user = self.request.user
            if not user.is_authenticated:
                raise PermissionDenied(
                    'Для фильтра "my" требуется авторизация.',
                )
            return queryset.filter(user=user)
        return queryset

    def filter_search(
        self,
        queryset: QuerySet[Question],
        name: str,
        value: Optional[str],
    ) -> QuerySet[Question]:
        """Поиск по title и description.

        (частичное совпадение, без учёта регистра).
        """
        if not value or not value.strip():
            return queryset
        query = value.strip()
        return queryset.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query),
        )
