from django import forms

from qna.forms import ImageAdminForm
from users.models import User


class UserImageAdminForm(ImageAdminForm):
    """Форма для загрузки и удаления изображения в модель юзера."""

    clear_image = forms.BooleanField(
        required=False,
        label='Удалить изображение',
        help_text='Отметьте, чтобы удалить изображение.'
    )

    class Meta:
        model = User
        fields = '__all__'
