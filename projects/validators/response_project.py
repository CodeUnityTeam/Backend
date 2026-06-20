"""Валидаторы для откликов и приглашений на проекты."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.constants.projects import (
    APPLICANT,
    APPROVED,
    AUTHOR,
    PENDING,
    PUBLISHED,
    REJECTED,
    WITHDRAWN,
)
from projects.models import Project, ProjectParticipant, Response

User = get_user_model()


def validate_can_create_response(
    project: Project,
    user: User,
) -> None:
    """Валидация перед созданием отклика на проект.

    Проверяет:
    - пользователь имеет роль worker
    - пользователь не является автором проекта
    - проект опубликован
    - нет существующего отклика от этого пользователя
    """
    if user.projects_relation != User.ProjectsRelationChoices.WORKER:
        raise serializers.ValidationError(
            'Откликаться на проекты могут только пользователи '
            'с ролью "worker".',
        )
    if project.author == user:
        raise serializers.ValidationError(
            'Нельзя откликнуться на собственный проект.',
        )
    if project.status_project != PUBLISHED:
        raise serializers.ValidationError(
            f'Отклик возможен только на проекты '
            f'со статусом "{PUBLISHED}".',
        )
    if Response.objects.filter(project=project, user=user).exists():
        raise serializers.ValidationError(
            'Вы уже откликнулись на этот проект.',
        )


def validate_can_invite(
    project: Project,
    inviter: User,
    invitee_id: str,
) -> User:
    """Валидация перед приглашением пользователя в проект.

    Проверяет:
    - приглашающий — автор проекта
    - приглашаемый пользователь существует
    - приглашаемый не является автором проекта
    - нет существующего отклика/приглашения

    Args:
        project: проект, в который приглашают.
        inviter: пользователь, который приглашает.
        invitee_id: UUID приглашаемого пользователя.

    """
    if project.author != inviter:
        raise serializers.ValidationError(
            'Только автор проекта может приглашать пользователей.',
        )
    try:
        invitee = User.objects.get(user_id=invitee_id)
    except User.DoesNotExist:
        raise serializers.ValidationError(
            {'user_id': 'Пользователь с таким ID не найден.'},
        )
    if project.author == invitee:
        raise serializers.ValidationError(
            'Нельзя пригласить автора проекта.',
        )
    if Response.objects.filter(project=project, user=invitee).exists():
        raise serializers.ValidationError(
            'Приглашение или отклик для этого пользователя '
            'уже существует.',
        )
    return invitee


def validate_status_can_be_changed(user_response: Response) -> None:
    """Проверяет, что статус отклика можно изменить.

    Статус можно изменить только если текущий статус — 'pending'.
    """
    if user_response.status_resp != PENDING:
        raise serializers.ValidationError(
            f'Статус можно изменить только из "{PENDING}", '
            f'текущий статус: "{user_response.status_resp}".',
        )


def validate_can_change_status(
    user_response: Response,
    user: User,
    new_status: str,
) -> None:
    """Валидация прав на изменение статуса отклика/приглашения.

    ┌──────────────────────┬──────────────┬──────────────────────────┐
    │ Тип отклика          │ Действие     │ Кто может                │
    ├──────────────────────┼──────────────┼──────────────────────────┤
    │ APPLICANT (отклик)   │ approved     │ автор-employer           │
    │ APPLICANT (отклик)   │ rejected     │ автор-employer           │
    │ APPLICANT (отклик)   │ withdrawn    │ соискатель-worker        │
    ├──────────────────────┼──────────────┼──────────────────────────┤
    │ AUTHOR (приглашение) │ approved     │ приглашённый-worker      │
    │ AUTHOR (приглашение) │ rejected     │ приглашённый-worker      │
    │ AUTHOR (приглашение) │ withdrawn    │ автор-employer           │
    └──────────────────────┴──────────────┴──────────────────────────┘
    Дополнительно:
      - текущий статус должен быть 'pending'
      - при одобрении — пользователь не должен быть участником проекта
    """
    validate_status_can_be_changed(user_response)
    is_employer = (
        user.projects_relation == User.ProjectsRelationChoices.EMPLOYER
    )
    is_worker = user.projects_relation == User.ProjectsRelationChoices.WORKER
    is_target_user = user_response.user == user
    is_project_author = user_response.project.author == user
    has_permission = False
    if new_status in (APPROVED, REJECTED):
        if (
            user_response.initiator_type == APPLICANT
            and is_project_author
            and is_employer
        ):
            has_permission = True
        elif (
            user_response.initiator_type == AUTHOR
            and is_target_user
            and is_worker
        ):
            has_permission = True

    elif new_status == WITHDRAWN:
        if (
            user_response.initiator_type == APPLICANT
            and is_target_user
            and is_worker
        ):
            has_permission = True
        elif (
            user_response.initiator_type == AUTHOR
            and is_project_author
            and is_employer
        ):
            has_permission = True
    if not has_permission:
        error_messages = {
            APPROVED: 'Нет прав для одобрения этого отклика/приглашения.',
            REJECTED: 'Нет прав для отклонения этого отклика/приглашения.',
            WITHDRAWN: 'Инициатор может отозвать свой отклик/приглашение.',
        }
        raise serializers.ValidationError(
            error_messages.get(
                new_status,
                f'Нет прав для действия "{new_status}".',
            ),
        )
    if new_status == APPROVED and ProjectParticipant.objects.filter(
        project=user_response.project,
        user=user_response.user,
    ).exists():
        raise serializers.ValidationError(
            'Пользователь уже является участником проекта.',
        )
