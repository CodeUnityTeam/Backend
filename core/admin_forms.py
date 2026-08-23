from django import forms
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

    class Meta:
        model = None
        fields = ('file',)

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
