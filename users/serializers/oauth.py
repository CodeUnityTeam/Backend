import logging
from typing import Any

from dj_rest_auth.registration.serializers import SocialLoginSerializer
from requests.exceptions import RequestException
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from users.models import User

logger = logging.getLogger(__name__)


class SocialAuthCodeRequestSerializer(serializers.Serializer):
    """Сериализатор для авторизации через OAuth2."""

    code = serializers.CharField(
        required=True,
        help_text=(
            'Код авторизации (Authorization Code), полученный от '
            'OAuth-провайдера на фронтенде.'
        ),
    )


class SafeSocialLoginSerializer(SocialLoginSerializer):
    """Сериализатор для безопасного входа через соцсети.

    Устраняет RelatedObjectDoesNotExist при автоматическом
    связывании аккаунтов по Email и обрабатывает сетевые сбои.
    """

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверяет данные кода и связывает пользователя."""
        try:
            # Запускаем оригинальную валидацию dj-rest-auth
            attrs = super().validate(attrs)
        except AttributeError as exc:
            # Ловим ошибку связи базы данных
            if type(exc).__name__ == 'RelatedObjectDoesNotExist':
                request = self._get_request()
                user: User | None = getattr(request, 'user', None)

                if user and not user.is_anonymous:
                    attrs['user'] = user
                    return attrs
            raise exc
        except RequestException as exc:
            # Перехватываем любые сетевые тайм-ауты сторонних соцсетей
            # и превращаем их в чистую ошибку 400 DRF
            raise ValidationError(
                {
                    'non_field_errors': [
                        'Внешний сервис авторизации временно недоступен. '
                        'Пожалуйста, попробуйте позже.',
                    ],
                },
            ) from exc
        except Exception as exc:
            raise exc

        return attrs


class SocialAuthUrlResponseSerializer(serializers.Serializer):
    """Сериализатор для возврата URL авторизации."""

    authorization_url = serializers.URLField(
        help_text='Url перенаправления пользователя на сторону провайдера.',
    )
