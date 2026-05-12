from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_groups(sender, **kwargs):
    """Создаёт стандартные группы пользователей после миграций."""
    from core.constants.users import DEFAULT_GROUP_NAMES
    from django.contrib.auth.models import Group

    for group_name in DEFAULT_GROUP_NAMES:
        Group.objects.get_or_create(name=group_name)


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        post_migrate.connect(create_default_groups, sender=self)
