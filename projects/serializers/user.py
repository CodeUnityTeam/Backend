from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserBaseSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя — для обычных пользователей в проекте."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('user_id', 'full_name', 'avatar_url')

    def get_full_name(self, user: User) -> str:
        """Получаем полное имя пользователя."""
        return f'{user.first_name} {user.last_name}'.strip()


class UserAuthorShortSerializer(UserBaseSerializer):
    """Краткий сериализатор для автора — дополняется последней активностью."""

    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserBaseSerializer.Meta.fields + ('last_activity_at',)

    def get_last_activity_at(self, user: User) -> str:
        """Метод для выдачи последней активности пользователя."""
        if user.last_login:
            return user.last_login.isoformat()
        return None


class UserAuthorSerializer(UserAuthorShortSerializer):
    """Сериализатор для автора проекта — дополнительные поля."""

    class Meta:
        model = User
        fields = UserAuthorShortSerializer.Meta.fields + ('email', 'phone')


