from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    OauthProvider,
    Skill,
    Specialization,
    User,
    UserSkill,
    UserSpecialization,
)


@admin.register(OauthProvider)
class OauthProviderAdmin(admin.ModelAdmin):
    """Админ-панель для модели провайдеров OAuth."""

    list_display = ('provider_id', 'name')
    search_fields = ('name',)


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    """Админ-панель для модели специализаций."""

    list_display = ('spec_id', 'name')
    search_fields = ('name',)


@admin.register(UserSpecialization)
class UserSpecializationAdmin(admin.ModelAdmin):
    """Админ-панель для связи пользователей и специализаций."""

    list_display = ('user', 'specialization')
    list_filter = ('specialization',)
    search_fields = ('user__email', 'specialization__name')


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    """Админ-панель для модели навыков."""

    list_display = ('skill_id', 'name')
    search_fields = ('name',)


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    """Админ-панель для связи пользователей и навыков."""

    list_display = ('user', 'skill')
    list_filter = ('skill',)
    search_fields = ('user__email', 'skill__name')


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Админ-панель для модели пользователя с расширенными полями."""

    list_display = (
        'user_id',
        'email',
        'first_name',
        'last_name',
        'role',
        'provider',
        'is_email_confirmed',
    )
    list_filter = ('role', 'provider', 'is_email_confirmed')
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
                    'avatar_url',
                ),
            },
        ),
        (
            'Права и статусы',
            {
                'fields': (
                    'role',
                    'provider',
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
