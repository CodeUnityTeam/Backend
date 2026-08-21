from typing import Any, Optional

from django.apps import apps
from django.contrib import admin
from django.db import models
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from core.admin_forms import ImageAdminForm

User = apps.get_model('users', 'User')


class RolePermissionsMixin:
    """Миксин для проверки прав в админке в зависимости от роли."""

    def _check_permission(self, request: HttpRequest, action: str) -> bool:
        """Проверка прав."""
        user = request.user

        if user.is_superuser or user.role == User.RoleChoices.ADMIN:
            return True

        if action == 'view':
            return True
        if action == 'add':
            return False
        if self.model._meta.app_label in ['users', 'feedback']:
            return not action
        return True

    def has_add_permission(
            self,
            request: HttpRequest,
            obj: Optional[Model]=None,
    ) -> bool:
        """Проверка прав на добавление объектов."""
        return self._check_permission(request, 'add')

    def has_change_permission(
            self,
            request: HttpRequest,
            obj: Optional[Model]=None,
    ) -> bool:
        """Проверка прав на изменение объектов."""
        return self._check_permission(request, 'change')

    def has_delete_permission(
            self,
            request: HttpRequest,
            obj: Optional[Model]=None,
    ) -> bool:
        """Проверка прав на удаление объектов."""
        if obj and hasattr(obj, 'pk') and obj.pk == request.user.pk:
            return False
        return self._check_permission(request, 'delete')

    def has_view_permission(
            self,
            request: HttpRequest,
            obj: Optional[Model]=None,
    ) -> bool:
        """Проверка прав на просмотр объектов."""
        return self._check_permission(request, 'view')

    def has_module_permission(self, request: HttpRequest) -> bool:
        """Проверка прав на вход в админку."""
        if request.user.is_staff and request.user.is_active:
            return True
        return False


class BaseLikeInline(admin.TabularInline):
    """Базовый инлайн для управления лайками в админке.

    Позволяет просматривать, добавлять и удалять лайки.
    Редактирование лайка запрещено (только создание/удаление).
    """

    extra = 0
    fields = ('user', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)
    verbose_name = 'Лайк'
    verbose_name_plural = 'Лайки'

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Optional[Model] = None,
    ) -> bool:
        """Запрет на редактирование лайка."""
        return False


class LikeCountMixin:
    """Миксин для ModelAdmin, добавляющий кол-во лайков в list_display."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Аннотирует каждый объект количеством лайков."""
        return super().get_queryset(request).annotate(
            _like_count=models.Count('likes'),
        )

    @admin.display(description='Кол-во лайков')
    def like_count(self, obj: Model) -> int:
        """Возвращает количество лайков для объекта."""
        return getattr(obj, '_like_count', 0)


class BaseImageInline(admin.TabularInline):
    """Базовый класс для inline-классов для изображений."""

    form = ImageAdminForm
    extra = 0
    fields = ('post_image', 'image_url', 'file')
    readonly_fields = ('post_image', 'image_url')
    can_delete = True

    def get_formset(
        self,
        request: HttpRequest,
        obj: Optional[Model] = None,
        **kwargs: Any,
    ) -> Any:
        """Задаёт тип медиа для валидации загружаемого файла."""
        formset = super().get_formset(request, obj, **kwargs)
        media_type = getattr(self, 'media_type', None)
        formset.form = type(
            'DynamicCoverForm',
            (formset.form,),
            {'_media_type': media_type},
        )
        return formset
