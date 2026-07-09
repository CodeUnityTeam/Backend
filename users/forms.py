from django import forms

from qna.forms import ImageAdminForm
from users.models import User


class UserImageAdminForm(ImageAdminForm):
    """Форма для загрузки и удаления изображения в модель юзера."""

    clear_image = forms.BooleanField(
        required=False,
        label='Удалить изображение',
        help_text='Отметьте, чтобы удалить изображение.',
    )

    class Meta:
        model = User
        fields = '__all__'


class UserAdminAddForm(UserImageAdminForm):
    """Форма для создания пользователя в админке с полями пароля."""

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Введите тот же пароль ещё раз.',
    )

    class Meta(UserImageAdminForm.Meta):
        pass

    def clean_password2(self) -> str:
        """Проверка, что пароли совпадают."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают.')
        return password2

    def save(self, commit: bool = True) -> User:
        """Создаёт пользователя с установкой пароля."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
