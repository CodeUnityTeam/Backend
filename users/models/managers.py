from typing import Any

from django.contrib.auth.base_user import BaseUserManager

from users.models import User


class UserManager(BaseUserManager):
    """Переопределение стандартного менеджера для создания пользователя.

    Поле username убрано из обязательных.
    """

    def create_user(
            self,
            email: str,
            password: str,
            **extra_fields: dict[str, Any],
    ) -> User:
        """Создает и сохраняет обычного пользователя."""
        if not email:
            raise ValueError('Поле email не может быть пустым!')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
            self,
            email: str,
            password: str,
            **extra_fields: dict[str, Any],
    ) -> User:
        """Создает и сохраняет суперпользователя."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)
