import re

from django.core.exceptions import ValidationError

from core.constants import ZERO_SYMBOL


def validate_location(location: str) -> str:
    """Валидатор для локации проекта (location).

    - буквы (A-Za-z, А-Яа-я)
    - цифры (0-9)
    - пробелы
    - дефисы (-)
    """
    stripped_loc = location.strip()
    if len(stripped_loc) == ZERO_SYMBOL:
        raise ValidationError('Локация не может быть пустым.')
    if not re.match(r'^[a-zA-Zа-яА-Я0-9\s\-]+$', stripped_loc):
        raise ValidationError(
            'Локация может содержать '
            'только буквы, цифры, пробелы, дефисы.',
        )
