import hashlib
import logging
from typing import Any

from django.core.cache import cache
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from core.throttling import FeedbackRateThrottle
from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import (
    CACHE_KEY_REVIEWS_PREFIX,
    REVIEW_DETAIL_CACHE_TIMEOUT,
    REVIEW_LIST_CACHE_TIMEOUT,
)
from feedback.permissions import CanEditDeleteReview
from feedback.selectors import get_reviews_queryset
from feedback.serializers import (
    FeedbackCreateSerializer,
    ReviewCreateSerializer,
    ReviewDetailSerializer,
    ReviewListSerializer,
    ReviewUpdateSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['Reviews'],
        summary='Список отзывов',
        description='Возвращает список всех отзывов.',
    ),
    create=extend_schema(
        tags=['Reviews'],
        summary='Создать отзыв',
        description='Создаёт новый отзыв от текущего пользователя.',
    ),
    retrieve=extend_schema(
        tags=['Reviews'],
        summary='Детальный отзыв',
        description='Возвращает детальную информацию об отзыве.',
    ),
    partial_update=extend_schema(
        tags=['Reviews'],
        summary='Редактировать отзыв',
        description='Редактирует текст отзыва (только автор).',
    ),
    destroy=extend_schema(
        tags=['Reviews'],
        summary='Удалить отзыв',
        description='Удаляет отзыв (только автор).',
    ),
)
class ReviewViewSet(CacheRetrieveMixin, viewsets.ModelViewSet):
    """Представление для отзывов."""

    queryset = get_reviews_queryset()
    http_method_names = ('get', 'post', 'patch', 'delete')
    retrieve_cache_timeout = REVIEW_DETAIL_CACHE_TIMEOUT
    retrieve_cache_key_prefix = CACHE_KEY_REVIEWS_PREFIX

    def get_permissions(self) -> BasePermission:
        """Назначает разные права для разных действий.

        - list, retrieve: любой пользователь (включая анонимных)
        - create: только авторизованные
        - partial_update, destroy: только автор отзыва
        """
        if self.action in ('list', 'retrieve'):
            return (AllowAny(),)
        if self.action in ('partial_update', 'destroy'):
            return (IsAuthenticated(), CanEditDeleteReview())
        return (IsAuthenticated(),)

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Возвращает класс сериализатора в зависимости от действия."""
        if self.action == 'list':
            return ReviewListSerializer
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        if self.action == 'partial_update':
            return ReviewUpdateSerializer
        return ReviewCreateSerializer

    def list(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Кэширует список отзывов.

        Ключ: reviews:list:{md5(params)} — без user_id, т.к. данные публичные
        (ReviewListSerializer не содержит персонализированных полей).
        """
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(
            str(sorted_params).encode(),
        ).hexdigest()
        cache_key = f'{CACHE_KEY_REVIEWS_PREFIX}:list:{params_str}'
        cached_response = cache.get(cache_key)
        logger.info(
            'Запрос списка отзывов: cache_key=%s',
            cache_key,
        )
        if cached_response is not None:
            logger.info(
                'Передача списка отзывов из кеша: cache_key=%s',
                cache_key,
            )
            return Response(cached_response)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=REVIEW_LIST_CACHE_TIMEOUT,
            )
            logger.info(
                'Кэширование списка отзывов, передача пользователю: '
                'cache_key=%s',
                cache_key,
            )
        return response

    @extend_schema(
        request=ReviewCreateSerializer,
        responses=ReviewDetailSerializer,
    )
    def create(self, request: Request) -> Response:
        """Создаёт отзыв."""
        logger.info(
            'Запрос на создание отзыва: user_id=%s',
            request.user.pk,
        )
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        logger.info(
            'Отзыв успешно создан: user_id=%s, review_id=%s',
            request.user.pk,
            review.review_id,
        )
        return Response(
            ReviewDetailSerializer(review).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=ReviewUpdateSerializer,
        responses=ReviewDetailSerializer,
    )
    def partial_update(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Обновляет отзыв частично."""
        review = self.get_object()
        logger.info(
            'Запрос на обновление отзыва: user_id=%s, review_id=%s',
            request.user.pk,
            review.pk,
        )
        serializer = ReviewUpdateSerializer(
            review,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        logger.info(
            'Отзыв успешно обновлен: user_id=%s, review_id=%s',
            request.user.pk,
            review.pk,
        )
        return Response(
            ReviewDetailSerializer(review).data,
            status=status.HTTP_200_OK,
        )

    def destroy(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Удаляет отзыв."""
        review = self.get_object()
        logger.info(
            'Запрос на удаление отзыва: user_id=%s, review_id=%s',
            request.user.pk,
            review.review_id,
        )
        response = super().destroy(request, *args, **kwargs)
        logger.info(
            'Отзыв успешно удален: user_id=%s, review_id=%s',
            request.user.pk,
            review.review_id,
        )
        return response


@extend_schema_view(
    create=extend_schema(tags=['Feedbacks'], summary='Дать обратную связь'),
)
class FeedbackViewSet(viewsets.ModelViewSet):
    """Представление для формы обратной связи."""

    permission_classes = (IsAuthenticated,)
    http_method_names = ('post',)
    throttle_classes = [FeedbackRateThrottle]

    @extend_schema(
        request=FeedbackCreateSerializer,
        responses=FeedbackCreateSerializer,
    )
    def create(self, request: Request) -> Response:
        """Создаёт обратную связь."""
        logger.info(
            'Запрос на создание обратной связи: user_id=%s',
            request.user.pk,
        )
        serializer = FeedbackCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)
