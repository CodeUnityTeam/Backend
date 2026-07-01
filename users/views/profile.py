import hashlib
import uuid
from typing import Any, Type

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.pagination import BasePagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from config import settings
from core.cache_mixins import CacheRetrieveMixin
from core.constants.cache import (
    USER_PROFILE_CACHE_TIMEOUT,
    USER_PROFILE_LIST_CACHE_TIMEOUT,
)
from users.filters import UserFilter
from users.models.users import User, UserExperience, UserLike
from users.pagination import ProfileListPagination
from users.permissions import IsEmployer
from users.serializers.profile import (
    AvatarUploadSerializer,
    DRFErrorResponseSerializer,
    DetailUserProfileSerializer,
    MeProfileRetrieveSerializer,
    MeProfileUpdateSerializer,
    PublicUserProfileSerializer,
    UserExperienceSerializer,
    UserLikeSerializer,
    UserResponseCardSerializer,
)
from users.services import (
    avatar_delete_handler,
    avatar_upload_handler,
    deactivate_user_account,
    get_profiles_for_employer_service,
)

UserModel = get_user_model()


# ============================== MeProfile ===================================

@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля авторизованного пользователя',
        responses={200: MeProfileRetrieveSerializer},
        description=(
            'Возвращает полную информацию о профиле. Поле experiences '
            'доступно только для чтения. Для изменения опыта работы '
            'используйте эндпоинт: /profile/me/experience/'
        ),
    ),
    patch=extend_schema(
        tags=['profile'],
        summary='Частично обновить данные авторизованного пользователя',
        request=MeProfileUpdateSerializer,
        responses={200: MeProfileRetrieveSerializer},
        description=(
            'Позволяет изменить доступные текстовые поля и списки ID '
            'навыков, специализаций и форматов. Не обновляет email '
            '(для него есть /profile/email-change/) и опыт работы '
            '(для него есть /profile/me/experience/).'
        ),
    ),
    delete=extend_schema(
        tags=['profile'],
        summary='Мягкое удаление аккаунта текущего пользователя',
        description=(
            '- Переводит обращение обратной связи в статус Closed'
            '- Переводит проекты в статус ARCHIVED'
            '- Удаляет записи участия в проектах'
            '- Удаляет отклики пользователя на проекты'
            '- Сбрасывает активность пользователя и верификацию email'
        ),
        request=None,
        responses={
            200: inline_serializer(
                name='CurrentUserDeleteSuccessResponse',
                fields={
                    'detail': serializers.CharField(
                        default='Аккаунт успешно удален.',
                    ),
                },
            ),
        },
    ),
)
@method_decorator(never_cache, name='dispatch')
class MeProfileView(RetrieveUpdateDestroyAPIView):
    """View для работы с профилем авторизованного пользователя."""

    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Вернуть объект текущего авторизованного пользователя."""
        return self.request.user

    def get_serializer_class(self) -> Type[serializers.Serializer]:
        """Возвращать разные сериализаторы для чтения и записи."""
        if self.request.method == 'PATCH':
            return MeProfileUpdateSerializer
        return MeProfileRetrieveSerializer

    def perform_destroy(self, instance: User) -> None:
        """Перевести флаги активности и согласия в False."""
        deactivate_user_account(instance)

    def delete(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Мягко удалить аккаунт и вернуть статус HTTP 200."""
        self.destroy(request, *args, **kwargs)
        return Response(
            {'detail': 'Аккаунт успешно удален.'},
            status=status.HTTP_200_OK,
        )


# ================================== Avatar ===================================

@extend_schema_view(
    post=extend_schema(
        summary='Загрузить аватар пользователя',
        description=(
            'Загрузка изображения (jpeg, jpg, png) размером до 10 МБ. '
            'Старый файл аватара автоматически удаляется из MinIO.'
        ),
        request={
            'multipart/form-data': inline_serializer(
                name='AvatarUploadRequest',
                fields={
                    'file': serializers.ImageField(help_text='Файл аватара'),
                },
            ),
        },
        responses={
            status.HTTP_201_CREATED: inline_serializer(
                name='AvatarUploadResponse',
                fields={'avatar_url': serializers.URLField()},
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
        tags=['Files'],
    ),
    delete=extend_schema(
        summary='Удалить аватар пользователя',
        description=(
            'Удаляет файл аватара из хранилища MinIO и '
            'очищает поле avatar_url в профиле пользователя.'
        ),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: OpenApiTypes.OBJECT,
        },
        tags=['Files'],
    ),
)
class UserAvatarAPIView(APIView):
    """API view для загрузки и удаления аватара пользователя."""

    permission_classes: list[type[IsAuthenticated]] = [IsAuthenticated]
    parser_classes: list[type[MultiPartParser]] = [MultiPartParser]
    allow_upload_size: int = settings.ALLOW_AVATAR_SIZE_MB * 1024 * 1024

    def post(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Response:
        """Загрузить новый аватар и удалить старый при наличии."""
        serializer: AvatarUploadSerializer = AvatarUploadSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        user: User = request.user  # type: ignore[valid-type]
        file_obj: UploadedFile = serializer.validated_data['file']

        public_url: str = avatar_upload_handler(user, file_obj)

        return Response(
            {'avatar_url': public_url}, status=status.HTTP_201_CREATED,
        )

    def delete(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Response:
        """Удаленить аватар."""
        user: User = request.user  # type: ignore[valid-type]

        if not user.avatar_url:
            return Response(
                {'detail': 'Аватар отсутствует.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avatar_delete_handler(user)

        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================ Experience =================================

@extend_schema_view(
    create=extend_schema(
        tags=['profile'],
        summary='Добавить запись об опыте работы',
        responses={201: UserExperienceSerializer},
    ),
    update=extend_schema(
        tags=['profile'],
        summary='Полностью обновить запись своего опыта',
        responses={200: UserExperienceSerializer},
    ),
    destroy=extend_schema(
        tags=['profile'],
        summary='Удалить запись своего опыта',
        responses={204: None},
    ),
)
class MeExperienceViewSet(ModelViewSet):
    """Управление опытом работы текущего авторизованного пользователя.

    Исключает метод PATCH, оперирует только своими записями.
    """

    serializer_class = UserExperienceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['post', 'put', 'delete']

    def get_queryset(self) -> QuerySet[UserExperience]:
        """Возвращает опыт работы только текущего пользователя."""
        return UserExperience.objects.filter(user=self.request.user)

    def perform_create(self, serializer: UserExperienceSerializer) -> None:
        """Автоматически привязывает опыт к текущему пользователю."""
        serializer.save(user=self.request.user)


# ============================== UserProfile ==================================

@extend_schema_view(
    get=extend_schema(
        tags=['profile'],
        summary='Получить данные профиля неавторизованного пользователя',
        description='Данные доступны по ID пользователя.',
        responses={200: DetailUserProfileSerializer},
    ),
)
class UserProfileView(CacheRetrieveMixin, RetrieveAPIView):
    """View для просмотра профиля пользователя по ID."""

    queryset = UserModel.objects.filter(is_active=True)
    serializer_class = DetailUserProfileSerializer
    permission_classes = [IsAuthenticated]
    retrieve_cache_timeout = USER_PROFILE_CACHE_TIMEOUT
    retrieve_cache_key_prefix = 'users'


# ================================ UserLikes ==================================


@method_decorator(never_cache, name='dispatch')
class ProfileLikeAPIView(APIView):
    """Эндпоинт для переключения лайка пользователю."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary='Переключение лайка пользователю',
        description=(
            'Позволяет поставить или убрать лайк пользователю. '
            'Если лайк уже стоял — он удаляется (is_liked: false). '
            'Если лайка не было — он создается (is_liked: true).'
        ),
        responses={
            200: inline_serializer(
                name='LikeDeletedResponse',
                fields={'is_liked': serializers.BooleanField(default=False)},
            ),
            201: inline_serializer(
                name='LikeCreatedResponse',
                fields={'is_liked': serializers.BooleanField(default=True)},
            ),
            400: inline_serializer(
                name='LikeValidationError',
                fields={
                    'detail': serializers.CharField(
                        default='Текст ошибки бизнес-логики.',
                    ),
                },
            ),
            401: inline_serializer(
                name='UnauthorizedError',
                fields={
                    'detail': serializers.CharField(
                        default='Учетные данные не были предоставлены.',
                    ),
                },
            ),
            404: inline_serializer(
                name='NotFoundError',
                fields={
                    'detail': serializers.CharField(
                        default='Страница не найдена.',
                    ),
                },
            ),
        },
    )
    def post(
        self,
        request: Request,
        worker_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Переключение (toggle) лайка для указанного worker_id."""
        employer = request.user
        worker = get_object_or_404(User, user_id=worker_id)

        # 1. Попытка удалить существующий лайк (Toggle-выключение)
        deleted_count, _ = UserLike.objects.filter(
            employer=employer,
            worker=worker,
        ).delete()

        if deleted_count > 0:
            return Response(
                {'is_liked': False},
                status=status.HTTP_200_OK,
            )

        # 2. Валидация бизнес-логики через сериализатор
        serializer = UserLikeSerializer(
            data={'worker': worker.user_id}, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        # 3. Создание лайка (Toggle-включение)
        serializer.save(employer=employer)

        return Response(
            {'is_liked': True},
            status=status.HTTP_201_CREATED,
        )


# =============================== ListProfile =================================


@extend_schema_view(
    get=extend_schema(
        summary='Получение списка профилей пользователей для автора проекта',
        description=(
            'Возвращает пагинированный список пользователей по сценариям: '
            'полный список, избранное или отклики на проекты автора запроса. '
            'Поддерживает фильтрацию по m2m-связям, текстовый поиск и '
            'различные стратегии сортировки.'
        ),
        tags=['profile'],
        parameters=[
            OpenApiParameter(
                name='responses',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    '`true` возвращает режим карточек откликов соискателей. '
                    'Взаимно исключает параметр `favourites`.'
                ),
            ),
            OpenApiParameter(
                name='favourites',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    '`true` возвращает только избранных соискателей, '
                    'которых лайкнул текущий наниматель. '
                    'Взаимно исключает параметр `responses`.'
                ),
            ),
            OpenApiParameter(
                name='sort_by',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=('newest', 'relevance', 'popularity'),
                description=(
                    'Критерий сортировки выдачи: '
                    'newest — по дате создания (значение по умолчанию), '
                    'relevance — по совпадению m2m-фильтров, '
                    'popularity — по количеству лайков соискателя.'
                ),
            ),
            OpenApiParameter(
                name='skill_ids',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Список UUID навыков через запятую.',
            ),
            OpenApiParameter(
                name='spec_ids',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Список UUID специализаций через запятую.',
            ),
            OpenApiParameter(
                name='format_ids',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Список UUID форматов работы через запятую.',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    'Текстовый поиск по подстроке по ФИО, стране и городу.'
                ),
            ),
        ],
        responses={
            200: PolymorphicProxySerializer(
                component_name='UserProfileUnion',
                serializers=[
                    PublicUserProfileSerializer,
                    UserResponseCardSerializer,
                ],
                resource_type_field_name=None,
            ),
            401: DRFErrorResponseSerializer,
            403: DRFErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                name='Пример ошибки 401 (Нет или недействительный токен)',
                value={'detail': 'Учетные данные не были предоставлены.'},
                status_codes=['401'],
            ),
            OpenApiExample(
                name='Пример ошибки 403 (Пользователь не EMPLOYER)',
                value={
                    'detail': 'У вас нет прав для выполнения этого действия.',
                },
                status_codes=['403'],
            ),
        ],
    ),
)
class UserProfileListView(ListAPIView):
    """View для получения списка профилей пользователей."""

    permission_classes: tuple[Type[BasePermission], ...] = (IsEmployer,)
    pagination_class: Type[BasePagination] = ProfileListPagination
    filter_backends: tuple[Type[DjangoFilterBackend], ...] = (
        DjangoFilterBackend,
    )
    filterset_class: Type[UserFilter] = UserFilter

    def get_serializer_class(self) -> Type[BaseSerializer]:
        """Динамически выбирает сериализатор на основе query-параметров."""
        params: dict[str, str] = self.request.query_params
        responses_param: str = params.get('responses', '').lower()

        if responses_param == 'true':
            return UserResponseCardSerializer

        return PublicUserProfileSerializer

    def get_queryset(self) -> QuerySet[User]:
        """Делегирует получение и фильтрацию QuerySet слою сервисов."""
        return get_profiles_for_employer_service(
            current_user=self.request.user,
            query_params=self.request.query_params,
        )

    def list(
        self, request: Request, *args: Any, **kwargs: Any,
    ) -> Response:
        """Кэширует список профилей.

        Ключ: users:list:{user_id}:{md5(params)}.
        user_id в ключе позволяет точечно инвалидировать кэш при лайке.
        """
        user = request.user
        query_params = request.query_params.dict()
        sorted_params = sorted(query_params.items())
        params_str = hashlib.md5(
            str(sorted_params).encode(),
        ).hexdigest()
        cache_key = f'users:list:{user.pk}:{params_str}'

        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(
                cache_key,
                response.data,
                timeout=USER_PROFILE_LIST_CACHE_TIMEOUT,
            )

        return response
