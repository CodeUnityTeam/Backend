from django.contrib import admin

from core.admin_mixins import RolePermissionsMixin

from .models import (
    Project,
    ProjectLike,
    ProjectParticipant,
    Response,
    WorkFormat,
)


@admin.register(Project)
class ProjectAdmin(RolePermissionsMixin, admin.ModelAdmin):
    """Админ-панель для модели проекта."""

    list_display = (
        'project_id',
        'author',
        'title',
        'short_desc',
        'status_project',
        'location',
    )
    filter_horizontal = ('skills', 'project_format', 'specializations')
    list_filter = ('author', 'location')
    search_fields = ('title ', 'short_desc')
    ordering = ('start_date',)


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


@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    """Админ‑панель для модели лайков."""

    list_display = (
        'project',
        'user',
    )
    search_fields =(
        'project__title',
        '^user__email',
    )
