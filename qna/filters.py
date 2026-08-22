from typing import Optional

import django_filters
from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotAuthenticated

from core.constants import MAX_SEARCH_UUIDS_SKILL_SPEC
from core.filters import UUIDInFilter
from core.validators import validators_search

from .models import Question


class QuestionFilter(django_filters.FilterSet):
    """Фильтр вопросов."""

    tags = UUIDInFilter(
        field_name='skills__skill_id',
        label='Теги (по ID навыков)',
        max_length=MAX_SEARCH_UUIDS_SKILL_SPEC,
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
            # likes_count уже аннотирован в get_question_list_queryset
            return queryset.order_by('-likes_count', '-created_at')
        if value == 'no_answers':
            # Вопросы без ответов
            # answers_count уже аннотирован в get_question_list_queryset
            return queryset.filter(answers_count=0)
        if value == 'my':
            user = self.request.user
            if not user.is_authenticated:
                raise NotAuthenticated(
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
        validators_search(value)
        query = value.strip()
        return queryset.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query),
        )
