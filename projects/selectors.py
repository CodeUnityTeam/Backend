from django.shortcuts import get_object_or_404

from .models import Project


def get_project_or_404(project_id: str) -> Project:
    """Получает проект по ID или выбрасывает 404, если не найден."""
    return get_object_or_404(Project, project_id=project_id)
