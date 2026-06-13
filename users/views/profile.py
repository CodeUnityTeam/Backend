from typing import Any, Type

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db.models import OuterRef, QuerySet, Subquery
from django.http import HttpRequest
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiTypes,
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
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from config import settings
from projects.models import Response as ProjectResponse
from users.filters import UserFilter
from users.models.users import User, UserExperience
from users.pagination import ProfileListPagination
from users.serializers.profile import (
    AvatarUploadSerializer,
    DetailUserProfileSerializer,
    MeProfileRetrieveSerializer,
    MeProfileUpdateSerializer,
    PublicUserProfileSerializer,
    UserExperienceSerializer,
    UserResponseListSerializer,
)
from users.services import avatar_delete_handler, avatar_upload_handler

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


class UserProfileListView(ListAPIView):
    """View для получения списка профилей пользователей."""

    permission_classes: list[Type[IsAuthenticated]] = [IsAuthenticated]
    pagination_class = ProfileListPagination
    filter_backends: list[Type[DjangoFilterBackend]] = [
        DjangoFilterBackend,
    ]
    filterset_class: Type[UserFilter] = UserFilter

    def get_serializer_class(self) -> Type[BaseSerializer]:
        """Динамически выбирает сериализатор на основе query-параметров."""
        params: dict[str, str] = self.request.query_params
        responses_param: str = params.get('responses', '').lower()

        if responses_param == 'true':
            return UserResponseListSerializer

        return PublicUserProfileSerializer

    def get_queryset(self) -> QuerySet[User]:
        """Возвращает аннотированный список пользователей для нанимателя."""
        current_user: Any = self.request.user

        if (
            current_user.projects_relation
            != User.ProjectsRelationChoices.EMPLOYER
        ):
            return User.objects.none()

        queryset: QuerySet[User] = User.objects.exclude(
            pk=current_user.pk,
        )
        params: dict[str, str] = self.request.query_params
        responses_param: str = params.get('responses', '').lower()

        if responses_param == 'true':
            user_responses: QuerySet[ProjectResponse] = (
                ProjectResponse.objects.filter(
                    user_id=OuterRef('pk'), project__author=current_user,
                )
            )

            queryset = queryset.annotate(
                annotated_initiator_type=Subquery(
                    user_responses.values('initiator_type')[:1],
                ),
                annotated_status_resp=Subquery(
                    user_responses.values('status_resp')[:1],
                ),
            )

        return queryset.prefetch_related(
            'skills', 'specializations', 'workformats', 'experiences',
        )
