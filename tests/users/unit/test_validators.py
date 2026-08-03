import pytest
from django.core.exceptions import ValidationError

from core.validators import file_size_validator


class DummyFile:
    """Заглушка для имитации структуры объекта UploadedFile."""

    def __init__(self, size_bytes: int) -> None:
        """Инициализирует фейковый файл с заданным размером в байтах."""
        self.size = size_bytes


def test_file_size_validator_passes_within_limit() -> None:
    """Валидатор успешно пропускает файл, если размер в пределах нормы."""
    # Настраиваем лимит в 5 МБ
    validator = file_size_validator(allow_size_mb=5)

    # Создаем файл размером 4 МБ
    valid_file = DummyFile(size_bytes=4 * 1024 * 1024)

    # Вызов не должен приводить к исключению
    result = validator(valid_file)  # type: ignore[arg-type]
    assert result == valid_file


def test_file_size_validator_fails_exceeding_limit() -> None:
    """Валидатор выбрасывает ValidationError при превышении лимита."""
    validator = file_size_validator(allow_size_mb=2)

    # Создаем файл размером 3 МБ (больше лимита в 2 МБ)
    invalid_file = DummyFile(size_bytes=3 * 1024 * 1024)

    # Ожидаем корректное бизнес-исключение Django
    with pytest.raises(ValidationError) as exc_info:
        validator(invalid_file)  # type: ignore[arg-type]

    assert 'Размер файла не должен превышать 2 МБ.' in str(exc_info.value)
