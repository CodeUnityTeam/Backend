from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Приложение пользователей."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    # TODO [USERS-14/15]: Написать тесты для users.
    #   Во всём приложении users нет ни одного теста.
    #   Критическая бизнес-логика (регистрация, смена email, мягкое удаление,
    #   загрузка аватара, OAuth) никак не проверяется.
    #   Решение: создать users/tests/ с тестами для моделей, сериализаторов и вьюх.
