from collections.abc import Callable

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


def file_size_validator(
    allow_size_mb: int,
) -> Callable[[UploadedFile], UploadedFile]:
    """Валидировать размер фвйла."""
    max_bytes: int = allow_size_mb * 1024 * 1024

    def validator(file_obj: UploadedFile) -> UploadedFile:
        if file_obj.size > max_bytes:
            msg: str = f"Размер файла не должен превышать {allow_size_mb} МБ."
            raise ValidationError(msg)
        return file_obj

    return validator
