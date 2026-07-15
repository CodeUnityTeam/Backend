from typing import Any, Optional

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import UploadedFile
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from core.admin_mixins import RolePermissionsMixin
from users.forms import UserAdminAddForm, UserImageAdminForm

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
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)
admin.site.unregister(EmailAddress)


class EmailConfirmedFilter(admin.SimpleListFilter):
    """Фильтр по подтверждённым email через Allauth EmailAddress."""

    title = 'Email подтверждён'
    parameter_name = 'email_confirmed'

    def lookups(
        self,
        request: HttpRequest,
        model_admin: admin.ModelAdmin,
    ) -> list[tuple[str, str]]:
        """Возвращает варианты фильтра: 'Да' и 'Нет'."""
        return (
            ('yes', 'Да'),
            ('no', 'Нет'),
        )

    def queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
    ) -> QuerySet:
        """Фильтрует пользователей по наличию подтверждённого EmailAddress."""
        if self.value() == 'yes':
            confirmed_users = (
                EmailAddress.objects
                .filter(verified=True)
                .values_list('user_id', flat=True)
            )
            return queryset.filter(user_id__in=confirmed_users)
        if self.value() == 'no':
            confirmed_users = (
                EmailAddress.objects
                .filter(verified=True)
                .values_list('user_id', flat=True)
            )
            return queryset.exclude(user_id__in=confirmed_users)
        return queryset


class BaseInline(admin.TabularInline):
    """Базовый класс для inline."""

    extra = 0


class UserSpecializationInline(BaseInline):
    """Inline для добавления специализаций юзеру."""

    model = UserSpecialization


class UserSkillInline(BaseInline):
    """Inline для добавления навыков юзеру."""

    model = UserSkill


class UserExperienceInline(BaseInline):
    """Inline для добавления опыта работы юзеру."""

    model = UserExperience


class EmailAddressInline(BaseInline):
    """Inline для добавления email адресов юзеру."""

    model = EmailAddress


class UserWorkFormatInline(BaseInline):
    """Inline для добавления форматов работы юзеру."""

    model = UserWorkFormat


@admin.register(Specialization)
class SpecializationAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели специализаций."""

    list_display = ('spec_id', 'name')
    search_fields = ('^name',)


@admin.register(Skill)
class SkillAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели навыков."""

    list_display = ('skill_id', 'name')
    search_fields = ('name',)


@admin.register(UserLike)
class UserLikeAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели лайков."""

    list_display = ('employer', 'worker')
    search_fields = ('^employer__email', 'worker__email')


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
        'get_email_confirmed',
        'get_rating',
    )
    list_filter = (
        'role',
        'workformats__name',
        'projects_relation',
        EmailConfirmedFilter,
    )
    search_fields = (
        'email',
        'first_name',
        'last_name',
        'phone_number',
        'experiences__company',
        'experiences__position',
        'specializations__name',
        'skills__name',
        )
    ordering = ('-created_at',)
    list_editable = ('role', 'projects_relation')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'new_email')}),
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
        ('Рейтинг пользователя', {'fields': ('rating',)}),
        (
            'Права и статусы',
            {
                'fields': (
                    'role',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'is_agreed_to_terms',
                ),
            },
        ),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
        ('Профессиональные данные', {'fields': ('projects_relation',)})
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
    readonly_fields = ('is_staff', 'is_superuser', 'get_avatar', 'rating')
    inlines = (
        UserSpecializationInline,
        UserSkillInline,
        UserWorkFormatInline,
        UserExperienceInline,
        EmailAddressInline,
    )

    def get_form(
            self,
            request: HttpRequest,
            obj: Optional[User] = None,
            **kwargs: Any,
    ) -> forms.ModelForm:
        """Замена формы для отображения кнопки загрузки аватара."""
        if obj is None:
            kwargs['form'] = UserAdminAddForm
        else:
            kwargs['form'] = UserImageAdminForm
        return super().get_form(request, obj, **kwargs)

    @admin.display(description='Аватар')
    def get_avatar(self, obj: User) -> str:
        """Метод для отображения аватара."""
        if obj.avatar_url:
            return format_html(
                '<img src="{}" style="max-height: 200px;">',
                obj.avatar_url,
            )
        return 'Не загружено'

    @admin.display(
            description=format_html('Email<br>подтверждён'),
            boolean=True,
        )
    def get_email_confirmed(self, obj: User) -> bool:
        """Возвращает статус подтверждения основного email пользователя."""
        try:
            email_address = EmailAddress.objects.get(user=obj, primary=True)
            return email_address.verified
        except EmailAddress.DoesNotExist:
            return False

    @admin.display(description=format_html('Рейтинг<br>пользователя'))
    def get_rating(self, obj: User) -> int:
        """Возвращает рейтинг пользователя."""
        return obj.rating

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
