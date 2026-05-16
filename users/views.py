from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from allauth.socialaccount.providers.mailru.views import MailRuOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from config.settings import SOCIALACCOUNT_PROVIDERS


class SocialLogin(SocialLoginView):
    """
    Базовый View для обработки запросов авторизации через сторонние приложения.
    """

    client_class = OAuth2Client


class GoogleLogin(SocialLogin):
    """View для обработки запросов авторизации через Google."""

    adapter_class = GoogleOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS["google"]["CALLBACK_URL"]


class YandexLogin(SocialLogin):
    """View для обработки запросов авторизации через Yandex."""

    adapter_class = YandexOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS["yandex"]["CALLBACK_URL"]


class MailRuLogin(SocialLogin):
    """View для обработки запросов авторизации через Mail.ru."""

    adapter_class = MailRuOAuth2Adapter
    callback_url = SOCIALACCOUNT_PROVIDERS["mailru"]["CALLBACK_URL"]
