from django.contrib import admin

from users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Административная панель пользователей."""

    list_display = (
        'user_id',
        'role',
    )
