from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class UniversalRateThrottle(AnonRateThrottle):
    """Комбинированный throttle.

    - Для авторизованных — как UserRateThrottle.
    - Для анонимов — как AnonRateThrottle.
    - Scope общий.
    """

    def __init__(self):
        super().__init__()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            # Для авторизованных: ключ по user.id
            ident = request.user.pk
            return self.cache_format % {
                'scope': self.scope,
                'ident': ident
            }
        else:
            # Для анонимов: ключ по IP (как в AnonRateThrottle)
            ident = self.get_ident(request)
            return self.cache_format % {
                'scope': self.scope,
                'ident': ident
            }


class LoginRateThrottle(UniversalRateThrottle):
    scope = 'login'


class RegisterRateThrottle(UniversalRateThrottle):
    scope = 'register'


class PasswordResetRateThrottle(UniversalRateThrottle):
    scope = 'password_reset'


class PasswordChangeRateThrottle(UserRateThrottle):
    scope = 'password_change'
