from rest_framework import serializers

from users.models import Skill


# TODO [QNA]: Дублирование SkillSerializer с projects/serializers.py:46.
#   В qna/serializers/tag.py определён SkillSerializer, который отличается
#   от SkillSerializer в projects/serializers.py:46:
#   - Здесь: fields = ['id', 'name'] (поле 'id' маппится через source='skill_id')
#   - Там: fields = ('skill_id', 'name')
#   Фронтенд будет получать разные форматы для одного и того же ресурса.
#   Решение: использовать единый SkillSerializer из users/serializers или
#   вынести общий сериализатор в core/.

class SkillSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов(скиллов)."""

    id = serializers.UUIDField(source='skill_id')

    class Meta:
        model = Skill
        fields = ['id', 'name']
