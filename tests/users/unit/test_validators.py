import pytest
from django.core.exceptions import ValidationError

from core.validators import file_validator
from minio.s3_utils import MediaType


class DummyFile:
    """Заглушка для имитации структуры объекта File/UploadedFile."""

    def __init__(self, size_bytes: int, content_type: str) -> None:
        """Инициализирует фейковый файл с размером и MIME-типом."""
        self.size = size_bytes
        self.content_type = content_type


def test_file_validator_passes_valid_file() -> None:
    """Валидатор пропускает файл, если размер и тип в норме."""
    # Для аватарок лимит 2 МБ (настроен в .env/settings)
    validator = file_validator(MediaType.AVATAR)

    # Создаем валидный файл: 1 МБ, формат png
    valid_file = DummyFile(
        size_bytes=1 * 1024 * 1024,
        content_type='image/png',
    )

    # Вызов не должен возвращать ничего (None) и не бросать исключений
    result = validator(valid_file)  # type: ignore[arg-type]
    assert result is None


def test_file_validator_fails_exceeding_limit() -> None:
    """Валидатор выбрасывает ValidationError при превышении лимита."""
    # Для аватарок лимит 2 МБ
    validator = file_validator(MediaType.AVATAR)

    # Создаем файл размером 3 МБ (больше лимита в 2 МБ)
    invalid_file = DummyFile(
        size_bytes=3 * 1024 * 1024,
        content_type='image/png',
    )

    with pytest.raises(ValidationError) as exc_info:
        validator(invalid_file)  # type: ignore[arg-type]

    assert 'Размер файла не должен превышать 2 МБ.' in str(
        exc_info.value,
    )


def test_file_validator_fails_unsupported_type() -> None:
    """Валидатор выбрасывает ValidationError при неверном MIME-типе."""
    # Для аватарок разрешены только картинки jpeg/png
    validator = file_validator(MediaType.AVATAR)

    # Создаем файл в пределах лимита (1 МБ), но с форматом pdf
    invalid_file = DummyFile(
        size_bytes=1 * 1024 * 1024,
        content_type='application/pdf',
    )

    with pytest.raises(ValidationError) as exc_info:
        validator(invalid_file)  # type: ignore[arg-type]

    assert 'Неподдерживаемый тип данных "application/pdf"' in str(
        exc_info.value,
    )
