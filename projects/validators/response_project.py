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

    Raises:
        serializers.ValidationError: если хотя бы одна проверка не пройдена.
    """
    if user.projects_relation != User.ProjectsRelationChoices.WORKER:
        raise serializers.ValidationError(
            'Откликаться на проекты могут только пользователи '
            'с ролью "Работник".',
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

    Returns:
        User: объект приглашаемого пользователя.

    Raises:
        serializers.ValidationError: если хотя бы одна проверка не пройдена.
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

    Raises:
        serializers.ValidationError: если статус не 'pending'.
    """
    if user_response.status_resp != PENDING:
        raise serializers.ValidationError(
            f'Статус можно изменить только из "{PENDING}", '
            f'текущий статус: "{user_response.status_resp}".',
        )


def get_response_permissions_map() -> dict[str, list[tuple[bool, str]]]:
    """Возвращает карту прав для изменения статуса отклика.

    Каждый элемент списка — кортеж (условие, сообщение_об_ошибке).
    Если хотя бы одно условие истинно — действие разрешено.

    Returns:
        dict: {
            'approved': [(условие1, ошибка1), (условие2, ошибка2)],
            'rejected': [...],
            'withdrawn': [...],
        }
    """
    return {
        APPROVED: [
            (
                lambda r, u: (
                    r.initiator_type == AUTHOR and r.user == u
                ),
                'Нет прав для одобрения этого приглашения.',
            ),
            (
                lambda r, u: (
                    r.initiator_type == APPLICANT
                    and r.project.author == u
                ),
                'Нет прав для одобрения этого отклика.',
            ),
        ],
        REJECTED: [
            (
                lambda r, u: (
                    r.initiator_type == AUTHOR and r.user == u
                ),
                'Нет прав для отклонения этого приглашения.',
            ),
            (
                lambda r, u: (
                    r.initiator_type == APPLICANT
                    and r.project.author == u
                ),
                'Нет прав для отклонения этого отклика.',
            ),
        ],
        WITHDRAWN: [
            (
                lambda r, u: (
                    r.initiator_type == APPLICANT and r.user == u
                ),
                'Только инициатор может отозвать свой отклик.',
            ),
            (
                lambda r, u: (
                    r.initiator_type == AUTHOR
                    and r.project.author == u
                ),
                'Только автор может отменить своё приглашение.',
            ),
        ],
    }


def validate_can_change_status(
    user_response: Response,
    user: User,
    new_status: str,
) -> None:
    """Валидация прав на изменение статуса отклика/приглашения.

    Проверяет:
    - текущий статус — 'pending'
    - у пользователя есть права на запрашиваемое действие
    - при одобрении — пользователь ещё не является участником проекта

    Raises:
        serializers.ValidationError: если хотя бы одна проверка не пройдена.
    """
    validate_status_can_be_changed(user_response)

    permissions_map = get_response_permissions_map()
    checks = permissions_map.get(new_status, [])

    if not any(check[0](user_response, user) for check in checks):
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