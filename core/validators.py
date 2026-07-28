import logging
from collections.abc import Callable
from pathlib import Path

import ahocorasick
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

CONSTANTS_DIR = Path(__file__).resolve().parent / 'constants'


def load_words(filename: str) -> list[str]:
    """Загружает слова из .txt (одно слово на строку)."""
    filepath = CONSTANTS_DIR / filename
    if not filepath.exists():
        return []
    return [
        line.strip().lower()
        for line in filepath.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]


# Загружаем списки слов
CURSE_WORDS: list[str] = load_words('ru_curse_words.txt')
ABUSIVE_WORDS: list[str] = load_words('ru_abusive_words.txt')
EXCEPTION_WORDS: list[str] = load_words('ru_exception_words.txt')

# Автомат Ахо-Корасик для поиска стоп-слов
CURSE_AUTO = ahocorasick.Automaton()
for word in CURSE_WORDS + ABUSIVE_WORDS:
    CURSE_AUTO.add_word(word, word)
CURSE_AUTO.make_automaton()

# Автомат для исключений
EXCEPTION_AUTO = ahocorasick.Automaton()
for word in EXCEPTION_WORDS:
    EXCEPTION_AUTO.add_word(word, word)
EXCEPTION_AUTO.make_automaton()


def validate_no_bad_words(value: str) -> str:
    """Блокирует строку при наличии стоп-слов.

    Поиск через алгоритм Ахо-Корасик за O(n).
    Слова из ru_exception_words.txt не блокируются.

    """
    if not CURSE_WORDS and not ABUSIVE_WORDS:
        return value

    lower_value = value.lower()

    # Собираем все совпадения стоп-слов за O(n)
    curse_matches: list[tuple[int, int, str]] = []
    for end_idx, word in CURSE_AUTO.iter(lower_value):
        start_idx = end_idx - len(word) + 1
        curse_matches.append((start_idx, end_idx, word))

    if not curse_matches:
        return value

    # Собираем все совпадения исключений за O(n)
    exception_ranges: list[tuple[int, int]] = []
    for exc_end, exc_word in EXCEPTION_AUTO.iter(lower_value):
        exc_start = exc_end - len(exc_word) + 1
        exception_ranges.append((exc_start, exc_end))

    # Проверяем каждое стоп-слово — O(m), где m — количество совпадений
    for start_idx, end_idx, word in curse_matches:
        if is_excepted(start_idx, end_idx, exception_ranges):
            continue
        logger.warning(
            'Блокировка: найдено стоп-слово "%s" в "%s..."',
            word,
            value[:50],
        )
        raise ValidationError('Без плохих слов, пожалуйста')

    return value


def is_excepted(
    curse_start: int,
    curse_end: int,
    exception_ranges: list[tuple[int, int]],
) -> bool:
    """True, если стоп-слово перекрывается с исключением. O(k)."""
    for exc_start, exc_end in exception_ranges:
        # Если диапазоны пересекаются — это исключение
        if not (curse_end < exc_start or curse_start > exc_end):
            return True
    return False


def file_size_validator(
    allow_size_mb: int,
) -> Callable[[UploadedFile], UploadedFile]:
    """Валидировать размер файла."""
    max_bytes: int = allow_size_mb * 1024 * 1024

    def validator(file_obj: UploadedFile) -> UploadedFile:
        if file_obj.size > max_bytes:
            msg: str = f'Размер файла не должен превышать {allow_size_mb} МБ.'
            raise ValidationError(msg)
        return file_obj

    return validator
