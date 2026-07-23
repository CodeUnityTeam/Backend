from django.contrib import admin

from core.admin_mixins import (
    BaseLikeInline,
    LikeCountMixin,
    RolePermissionsMixin,
)

from .models import (
    Project,
    ProjectLike,
    ProjectParticipant,
    Response,
    WorkFormat,
)


class ProjectLikeInline(BaseLikeInline):
    """Инлайн для управления лайками проекта."""

    model = ProjectLike
    verbose_name = 'Лайк проекта'
    verbose_name_plural = 'Лайки проекта'


@admin.register(Project)
class ProjectAdmin(LikeCountMixin, RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели проекта."""

    list_display = (
        'project_id',
        'author',
        'title',
        'short_desc',
        'status_project',
        'location',
        'telegram_contact',
        'like_count',
    )
    filter_horizontal = ('skills', 'project_format', 'specializations')
    list_filter = ('author', 'location')
    search_fields = ('title', 'short_desc')
    ordering = ('start_date',)
    inlines = (ProjectLikeInline,)


@admin.register(ProjectParticipant)
class ProjectParticipantAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели участников проекта."""

    list_display = (
        'project',
        'user',
        'status_participant',
    )
    search_fields = ('^project__title', '^project__author')


@admin.register(Response)
class ResponseAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели октликов."""

    list_display = (
        'response_id',
        'project',
        'user',
        'initiator_type',
        'status_resp',
    )


@admin.register(WorkFormat)
class WorkFormatAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели форматов работы."""

    list_display = ('format_id', 'name')
    search_fields = ('name',)
