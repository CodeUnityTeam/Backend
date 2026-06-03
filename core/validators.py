from collections.abc import Callable
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


def file_size_validator(allow_size_mb: int) -> Callable[[Any], Any]:
    """Валидатор размера для одного файла или списка файлов."""
    max_bytes: int = allow_size_mb * 1024 * 1024

    def validator(value: Any) -> Any:
        items = value if isinstance(value, (list, tuple)) else [value]

        for obj in items:
            if isinstance(obj, UploadedFile) and obj.size > max_bytes:
                msg: str = (
                    f"Размер файла не должен превышать {allow_size_mb} МБ."
                )
                raise ValidationError(msg)
        return value

    return validator
