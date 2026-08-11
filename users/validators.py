# import re

from rest_framework.exceptions import ValidationError


def clear_text_data(value: str, field_name: str) -> str:
    """Очищает и нормализует текстовые данные пользователя.

    Применяется для обработки строк, полученных от сторонних OAuth-
    провайдеров, предотвращая попадание некорректных символов в БД.
    """
    # TODO: Реализовать очистку по спецификации ТЗ
    cleaned_value = value.strip()

    if not cleaned_value:
        default_values = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }
        return default_values.get(field_name, 'Пользователь')

    return cleaned_value


def process_and_verify_name(value: str) -> None:
    """Проверяет соответствие текстового значения правилам ТЗ.

    Возвращает очищенную строку или возбуждает исключение с текстом
    ошибки, сформированным на основе бизнес-требований.
    """
    # TODO: Реализовать валидацию и генерацию текста ошибок по ТЗ
    processed_value = value.strip()

    if not processed_value:
        raise ValueError('Поле не может быть пустым или состоять из пробелов.')


def validate_user_name(value: str) -> None:
    """Валидатор для проверки персональных данных (имени или фамилии).

    Проводит предварительный анализ строки перед сохранением данных,
    переданных пользователем напрямую через формы.
    """
    try:
        process_and_verify_name(value)
    except ValueError as exc:
        raise ValidationError(str(exc))


def validate_password_requirements(_value: str) -> None:
    """Проверяет соответствие пароля базовым символьным ограничениям.

    Вызывается до стандартных валидаторов Django для раннего отсечения
    паролей, содержащих запрещенные наборы символов.
    """
    # TODO: Реализовать проверку символьного состава по ТЗ
    # Пример: проверка на отсутствие кириллицы
    # if re.search(r'[А-Яа-яЁё]', value):
    #     raise ValidationError(
    #         'Пароль не должен содержать символы кириллицы.',
    #     )
