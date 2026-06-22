from typing import Any, Optional

from django import forms
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest
from django.utils.safestring import mark_safe

from core.admin_mixins import RolePermissionsMixin
from users.forms import UserImageAdminForm

from .models import (
    Skill,
    Specialization,
    User,
    UserExperience,
    UserLike,
    UserSkill,
    UserSpecialization,
    UserWorkFormat,
)
from .services import avatar_delete_handler, avatar_upload_handler

admin.site.unregister(Group)


class BaseInline(admin.TabularInline):
    """Базовый класс для inline."""

    extra = 0
    classes = ('collapse',)


class UserSpecializationInline(BaseInline):
    """Inline для добавления специализаций юзеру."""

    model = UserSpecialization


class UserSkillInline(BaseInline):
    """Inline для добавления навыков юзеру."""

    model = UserSkill


class UserWorkFormatInline(BaseInline):
    """Inline для добавления форматов работы юзеру."""

    model = UserWorkFormat


@admin.register(Specialization)
class SpecializationAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели специализаций."""

    list_display = ('spec_id', 'name')
    search_fields = ('^name',)


@admin.register(UserSpecialization)
class UserSpecializationAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для связи пользователей и специализаций."""

    list_display = ('user', 'specialization')
    list_filter = ('specialization',)
    search_fields = ('^user__email', '^specialization__name')


@admin.register(Skill)
class SkillAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели навыков."""

    list_display = ('skill_id', 'name')
    search_fields = ('name',)


@admin.register(UserSkill)
class UserSkillAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для связи пользователей и навыков."""

    list_display = ('user', 'skill')
    list_filter = ('skill',)
    search_fields = ('^user__email', '^skill__name')


@admin.register(UserExperience)
class UserExperienceAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели опыта работы."""

    list_display = (
        'exp_id',
        'user',
        'company',
        'position',
        'responsibilities',
        'start_date',
        'end_date',
        )
    list_filter = ('position',)
    search_fields = ('^user__email', 'company')


@admin.register(UserLike)
class UserLikeAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели лайков."""

    list_display = ('employer', 'worker')
    search_fields = ('^employer__email', 'worker__email')


@admin.register(UserWorkFormat)
class UserWorkFormatAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для связи пользователей и форматов работы."""

    list_display = ('user', 'workformat')
    list_filter = ('workformat',)
    search_fields = ('^user__email',)


@admin.register(User)
class UserAdmin(RolePermissionsMixin, DjangoUserAdmin):
    """Админ-панель для модели пользователя с расширенными полями."""

    form = UserImageAdminForm

    list_display = (
        'user_id',
        'email',
        'first_name',
        'last_name',
        'role',
        'projects_relation',
        'get_avatar',
        'is_email_confirmed',
    )
    list_filter = ('role', 'is_email_confirmed')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (
            'Персональные данные',
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'phone_number',
                    'additional_contact',
                    'country',
                    'city',
                    'about_me',
                ),
            },
        ),
        (
            'Аватар',
            {
                'fields': (
                    'get_avatar',
                    'file',
                    'avatar_url',
                    'clear_image',
                ),
            },
        ),
        (
            'Права и статусы',
            {
                'fields': (
                    'role',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'is_email_confirmed',
                    'is_password_confirmed',
                    'is_agreed_to_terms',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
        ('Смена email', {'fields': ('new_email',)}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'first_name',
                    'last_name',
                    'password1',
                    'password2',
                ),
            },
        ),
    )
    readonly_fields = ('is_staff', 'is_superuser', 'get_avatar')
    inlines = (
        UserSpecializationInline,
        UserSkillInline,
        UserWorkFormatInline,
    )

    def get_form(
            self,
            request: HttpRequest,
            obj: Optional[User] = None,
            **kwargs: Any,
    ) -> forms.ModelForm:
        """Замена формы для отображения кнопки загрузки аватара."""
        kwargs['form'] = UserImageAdminForm
        return super().get_form(request, obj, **kwargs)

    @admin.display(description='Аватар')
    @mark_safe
    def get_avatar(self, obj: User) -> str:
        """Метод для отображения аватара."""
        if obj.avatar_url:
            return f'<img src="{obj.avatar_url}" style="max-height: 100px;">'
        return ''

    def save_model(
        self,
        request: HttpRequest,
        obj: User,
        form: UserImageAdminForm,
        change: bool,
    ) -> None:
        """Сохранение модели."""
        # 1. Загрузка файла в БД
        image_obj: UploadedFile | None = form.cleaned_data.get('file')

        if image_obj:
            public_url: str = avatar_upload_handler(obj, file_obj=image_obj)
            obj.avatar_url = public_url

        # 2. Удаление аватара
        if form.cleaned_data.get('clear_image'):
            avatar_delete_handler(obj)

        # 3. Проверка состояния роли
        if 'role' in form.changed_data:
            if obj.role == 'admin':
                obj.is_staff = True
                obj.is_superuser = True
            elif obj.role == 'moderator':
                obj.is_staff = True
                obj.is_superuser = False
            else:
                obj.is_staff = False
                obj.is_superuser = False

        super().save_model(request, obj, form, change)
