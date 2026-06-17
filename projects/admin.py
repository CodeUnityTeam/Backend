from django.contrib import admin

from .models import Project, ProjectLike, ProjectParticipant


class ProjectParticipantInline(admin.TabularInline):
    """Инлайн для отображения участников проекта."""

    model = ProjectParticipant
    extra = 0
    verbose_name = 'Участник'
    verbose_name_plural = 'Участники'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Админка для модели Project."""

    list_display = (
        'title',
        'author',
        'status_project',
        'published_at',
        'created_at',
    )
    list_filter = ('status_project',)
    search_fields = (
        'title',
        'author__email',
    )
    readonly_fields = (
        'project_id',
        'published_at',
        'created_at',
        'updated_at',
    )
    filter_horizontal = (
        'skills',
        'specializations',
        'project_format',
    )
    inlines = (ProjectParticipantInline,)


@admin.register(ProjectParticipant)
class ProjectParticipantAdmin(admin.ModelAdmin):
    """Админка для модели ProjectParticipant."""

    list_display = (
        'project',
        'user',
        'status_participant',
    )
    list_filter = ('status_participant',)


@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    """Админка для модели ProjectLike."""

    list_display = (
        'user',
        'project',
        'created_at',
    )
