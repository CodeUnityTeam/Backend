from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import Project

User = get_user_model()


def get_project_or_404(project_id: str) -> Project:
    """Получает проект по ID или выбрасывает 404, если не найден."""
    return get_object_or_404(Project, project_id=project_id)


def can_archive_project(user: User, project: Project) -> bool:
    """Проверяет, может ли пользователь архивировать проект."""
    return (
        user.is_superuser or
        user.is_staff or
        project.author == user or
        user.role == 'admin'
    )
