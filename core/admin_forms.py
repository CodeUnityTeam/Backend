from typing import Any

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Model

from core.validators import file_validator
from minio.s3_utils import MediaType, S3Service


class AvatarAdminForm(forms.ModelForm):
    """Форма для загрузки аватара через админку."""

    file = forms.ImageField(
        required=False,
        label='Загрузить файл',
        help_text='Выберите изображение',
    )

    class Meta:
        model = None
        fields = ('file',)


class ImageAdminForm(forms.ModelForm):
    """Форма для загрузки изображения через админку."""

    file = forms.ImageField(
        required=False,
        label='Загрузить файл',
        help_text='Выберите изображение',
    )
    uploaded_by = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = None
        fields = ('file', 'uploaded_by')

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Инициализация формы с возможностью передачи parent_obj и request."""
        self.parent_obj = kwargs.pop('parent_obj', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.parent_obj:
            self.initial['uploaded_by'] = self.parent_obj.user
            self.fields['uploaded_by'].initial = self.parent_obj.user

    def clean(self) -> dict[str, Any]:
        """Очистка данных с подстановкой uploaded_by."""
        cleaned_data = super().clean()
        if self.parent_obj:
            cleaned_data['uploaded_by'] = self.parent_obj.user
        elif self.request:
            # При создании нового объекта parent_obj=None, поэтому пытаемся
            # получить пользователя из POST-данных родительской формы.
            # В админке Django имя поля — это просто название поля модели,
            # а не "{model_name}-{field_name}".
            user_id = self.request.POST.get('user')
            if not user_id:
                # Если поле называется иначе (например, с префиксом),
                # пробуем вариант с префиксом модели
                parent_model_name = self.instance._meta.model_name
                user_id = self.request.POST.get(f'{parent_model_name}-user')
            if user_id:
                User = apps.get_model('users', 'User')
                cleaned_data['uploaded_by'] = User.objects.get(pk=user_id)
        return cleaned_data

    def clean_file(self) -> UploadedFile | None:
        """Динамическая валидация размера и типа файла через S3Service."""
        file_obj: UploadedFile | None = self.cleaned_data.get('file')
        media_type: MediaType | None = getattr(self, '_media_type', None)

        # Если файл прикрепили и у формы задан тип медиа — валидируем
        if file_obj and media_type:
            try:
                file_validator(media_type)(file_obj)
            except ValidationError as err:
                # Перехватываем ошибку и передаем ее в форму админки
                raise forms.ValidationError(err.messages)

        return file_obj

    def save(self, commit: bool = True) -> Model:
        """Сохранение с загрузкой файла в S3."""
        instance = self.instance
        uploaded_by = self.cleaned_data.get('uploaded_by')
        if uploaded_by:
            instance.uploaded_by = uploaded_by
        file_obj: UploadedFile | None = self.cleaned_data.get('file')
        if file_obj:
            media_type: MediaType | None = getattr(self, '_media_type', None)
            if not media_type:
                raise ValueError(
                    f'В классе {self.__class__.__name__} '
                    f'не задан обязательный атрибут _media_type',
                )
            public_url: str = S3Service.upload(media_type, file_obj)
            instance.image_url = public_url
            instance.original_name = file_obj.name
            instance.file_size = file_obj.size
            instance.mime_type = file_obj.content_type or 'image/jpeg'

        if commit:
            instance.save()
        return instance
