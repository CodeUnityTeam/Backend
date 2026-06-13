from django.shortcuts import get_object_or_404
from rest_framework import serializers

from core.constants.projects import ALLOWED_STATUSED_FOR_LIKE
from projects.models import Project, ProjectLike


class ProjectLikeResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа после создани/удаления лайка."""

    liked = serializers.BooleanField()
    likes_count = serializers.IntegerField()


class ProjectLikeSerializer(serializers.Serializer):
    """Сериализатор для лайков."""

    def validate_project_id(self, project_id: str) -> str:
        """Используем готовую функцию для получения проекта или 404."""
        project = get_object_or_404(Project, project_id=project_id)
        if project.status_project not in ALLOWED_STATUSED_FOR_LIKE:
            raise serializers.ValidationError(
                'Нельзя лайкать проект с текущим статусом.',
            )
        self.context['project'] = project
        return project_id

    def toggle_like(self) -> dict:
        """Toggle-логика: создание/удаление лайка."""
        user = self.context['request'].user
        project = self.context['project']
        like_exists = ProjectLike.objects.filter(
            user=user,
            project=project,
        ).exists()
        if like_exists:
            ProjectLike.objects.filter(user=user, project=project).delete()
            liked = False
        else:
            ProjectLike.objects.create(user=user, project=project)
            liked = True
        return {
            'liked': liked,
            'likes_count': ProjectLike.objects.filter(project=project).count(),
        }
