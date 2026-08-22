import re

from rest_framework.exceptions import ValidationError

from core.constants.users import (
    INVALID_FIELD_ERROR,
    INVALID_PASSWORD_ERROR,
    PASSWORD_PATTERN,
    USER_FIRST_NAME_LENGTH,
    USER_LAST_NAME_LENGTH,
    USER_NAME_CLEANING_PATTERN,
    USER_NAME_VALIDATION_PATTERN,
)


def clear_text_data(value: str, field_name: str) -> str:
    """Очищает и нормализует текстовые данные пользователя из OAuth.

    Удаляет недопустимые символы, убирает дублирующиеся пробелы/дефисы,
    обрезает строку до максимальной длины по ТЗ и подставляет дефолтные
    значения, если результат оказался пустым.
    """
    if not isinstance(value, str):
        value = str(value) if value is not None else ''

    # 1. Удаляем все символы, кроме разрешенных по ТЗ
    cleaned_value = re.sub(USER_NAME_CLEANING_PATTERN, '', value)

    # 2. Нормализуем пробелы и дефисы (схлопываем повторяющиеся)
    cleaned_value = re.sub(
        r'\s+', ' ', cleaned_value,  # Заменяем несколько пробелов на один
    )
    cleaned_value = re.sub(
        r'-+', '-', cleaned_value,  # Заменяем несколько дефисов на один
    )

    # 3. Убираем пробелы и дефисы на краях строки
    # (например, если они остались после удаления спецсимволов)
    cleaned_value = cleaned_value.strip(' -')

    # 4. Если после очистки строка пустая — возвращаем дефолтное значение
    if not cleaned_value:
        default_values = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }
        return default_values.get(field_name, 'Пользователь')

    # 5. Обрезаем строку по максимальной длине согласно ТЗ
    max_lengths = {
        'first_name': USER_FIRST_NAME_LENGTH,
        'last_name': USER_LAST_NAME_LENGTH,
    }
    max_len = max_lengths.get(
        field_name, 35,  # По умолчанию 35, если прилетит неизвестное поле
    )

    # Обрезаем и на всякий случай еще раз убираем пробелы на конце,
    # если обрезка пришлась на пробел
    return cleaned_value[:max_len].strip(' -')


def validate_user_name(value: str) -> None:
    """Валидатор для проверки состава символов имени или фамилии."""
    # Латиница, кириллица (с Ёё), пробелы и дефисы
    if not re.match(USER_NAME_VALIDATION_PATTERN, value):
        raise ValidationError(INVALID_FIELD_ERROR)


def validate_password_requirements(value: str) -> None:
    """Валидатор для проверки состава и сложности символов пароля."""
    # 1. Только латиница, цифры и спецсимволы ASCII (без кириллицы и пробелов)
    if not re.match(PASSWORD_PATTERN, value):
        raise ValidationError(INVALID_PASSWORD_ERROR)

    # 2. Обязательно наличие строчной латинской буквы
    if not re.search(r'[a-z]', value):
        raise ValidationError(INVALID_PASSWORD_ERROR)

    # 3. Обязательно наличие заглавной латинской буквы
    if not re.search(r'[A-Z]', value):
        raise ValidationError(INVALID_PASSWORD_ERROR)

    # 4. Обязательно наличие хотя бы одной цифры
    if not re.search(r'[0-9]', value):
        raise ValidationError(INVALID_PASSWORD_ERROR)

    # 5. Обязательно наличие хотя бы одного спецсимвола.
    # Ищем любой символ, который НЕ является буквой и НЕ является цифрой
    if not re.search(r'[^A-Za-z0-9]', value):
        raise ValidationError(INVALID_PASSWORD_ERROR)
