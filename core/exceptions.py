import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

from users.adapters import ImmediateResponseException

logger = logging.getLogger(__name__)


class ProjectAPIException(APIException):
    """Базовое бизнес-исключение проекта.

    Все кастомные исключения наследуются от этого класса,
    что гарантирует их корректную обработку DRF.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Произошла ошибка'
    default_code = 'error'


class ConflictException(ProjectAPIException):
    """Исключение конфликта состояния (HTTP 409).

    Используется, когда запрос конфликтует с текущим состоянием ресурса,
    например при повторном приглашении уже приглашённого пользователя.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Конфликт с текущим состоянием ресурса.'
    default_code = 'conflict'


def custom_exception_handler(exc: Exception, context: dict) -> Response:
    """Кастомный обработчик исключений для проекта."""
    request = context.get('request')
    view = context.get('view')

    if isinstance(exc, ImmediateResponseException):
        response = exception_handler(exc, context)
        if response is not None:
            return response
        return Response(
            data=exc.detail,
            status=exc.status_code,
        )

    logger.exception(
        '%s: %s',
        type(exc).__name__,
        exc,
        extra={
            'method': request.method if request else None,
            'path': request.path if request else None,
            'user': request.user.id
            if request and request.user.is_authenticated
            else None,
            'view': view.__class__.__name__ if view else None,
        },
    )

    response = exception_handler(exc, context)

    if response is not None:
        return response

    return Response(
        {'detail': 'Internal server error'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
