from django import forms


class ImageAdminForm(forms.ModelForm):
    """Форма для загрузки изображения через админку."""

    file = forms.ImageField(
        required=False,
        label='Загрузить файл',
        help_text='Выберите изображение',
    )
