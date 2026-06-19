from typing import Optional

from django.db.models import Model
from django.http import HttpRequest


class RolePermissionsMixin:
    """Миксин для проверки прав в админке в зависимости от роли."""

    def _check_permission(self, request: HttpRequest, action: str) -> bool:
        """Проверка прав."""
        user = request.user

        role = getattr(user, 'role', None)
        if role not in ['admin', 'moderator']:
            return None
        if user.is_superuser or role == 'admin':
            return True

        if action == 'view':
            return True
        if action == 'add':
            return False
        if self.model._meta.app_label in ['users', 'feedback']:
            return not action
        return True

    def has_add_permission(self, request, obj=None):
        return self._check_permission(request, 'add')

    def has_change_permission(self, request, obj=None):
        return self._check_permission(request, 'change')

    def has_delete_permission(self, request, obj=None):
        if obj and hasattr(obj, 'pk') and obj.pk == request.user.pk:
            return False
        return self._check_permission(request, 'delete')

    def has_view_permission(self, request, obj=None):
        return self._check_permission(request, 'view')

    def has_module_permission(self, request):
        if request.user.is_staff and request.user.is_active:
            return True
        return False
