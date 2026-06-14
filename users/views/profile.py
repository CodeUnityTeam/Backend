from typing import Any, Type

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db.models import QuerySet
from django.http import HttpRequest
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    PolymorphicProxySerializer,
)
from rest_framework import serializers, status
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.pagination import BasePagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from config import settings
from users.filters import UserFilter
from users.models.users import User, UserExperience
from users.pagination import ProfileListPagination
from users.permissions import IsEmployer
from users.serializers.profile import (
    AvatarUploadSerializer,
    DetailUserProfileSerializer,
    DRFErrorResponseSerializer,
    MeProfileRetrieveSerializer,
    MeProfileUpdateSerializer,
    PublicUserProfileSerializer,
    UserExperienceSerializer,
    UserResponseCardSerializer,
)
from users.services import (
    avatar_delete_handler,
    avatar_upload_handler,
    get_profiles_for_employer_service
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
        instance.is_active = False
        instance.is_agreed_to_terms = False
        instance.save()

        EmailAddress.objects.filter(
            user=instance,
            email__iexact=instance.email,
        ).update(verified=False)

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
class UserProfileView(RetrieveAPIView):
    """View для просмотра профиля пользователя по ID."""

    queryset = UserModel.objects.filter(is_active=True)
    serializer_class = DetailUserProfileSerializer
    permission_classes = [IsAuthenticated]


# =============================== ListProfile =================================


@extend_schema_view(
    get=extend_schema(
        summary='Получение списка профилей пользователей для автора проекта',
        description=(
            'Возвращает список пользователей. При `responses=true` '
            'возвращает список карточек откликов пользователей на проекты '
            'текущего автора, дублируя карточки под каждый отклик.'
        ),
        tags=['profile'],
        parameters=[
            OpenApiParameter(
                name='responses',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    'При `true` переключает выдачу в режим карточек '
                    'откликов соискателей.'
                ),
            ),
            OpenApiParameter(
                name='sort_by',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=('newest', 'relevance'),
                description='Критерий сортировки выдачи.',
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
                description='Поиск по подстроке ФИО, стране и городу.',
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
                name='Пример ошибки 401 (Нет токена)',
                value={'detail': 'Учетные данные не были предоставлены.'},
                status_codes=['401'],
            ),
            OpenApiExample(
                name='Пример ошибки 403 (Пользователь не EMPLOYER)',
                value={
                    'detail': 'У вас нет прав для выполнения этого действия.'
                },
                status_codes=['403'],
            ),
        ],
    )
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
