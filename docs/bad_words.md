# 🛡️ Блокировка стоп-слов

В проектах, вопросах и ответах работает автоматическая проверка на нецензурную лексику и оскорбления.

## Алгоритм

Двухпроходный поиск через алгоритм Ахо-Корасик (O(n)):

1. **Сбор стоп-слов** — проход по тексту, поиск всех совпадений из `ru_curse_words.txt` + `ru_abusive_words.txt`
2. **Сбор исключений** — проход по тексту, поиск всех совпадений из `ru_exception_words.txt`
3. **Фильтрация** — если стоп-слово перекрывается по диапазону с исключением, оно пропускается. Иначе — `ValidationError`

## Файлы списков

Все списки находятся в [`core/constants/`](../core/constants/):

| Файл | Описание | Количество слов |
|---|---|---|
| [`ru_curse_words.txt`](../core/constants/ru_curse_words.txt) | Нецензурная лексика (мат) | 2189 |
| [`ru_abusive_words.txt`](../core/constants/ru_abusive_words.txt) | Оскорбления | 125 |
| [`ru_exception_words.txt`](../core/constants/ru_exception_words.txt) | Исключения (парикмахер, мандат, заштрихуй и др.) | 9 |

Файлы представляют собой обычный текст — одно слово на строку. Строки, начинающиеся с `#`, игнорируются.

## Валидатор

Функция [`validate_no_bad_words()`](../core/validators.py:59) применяется к текстовым полям через DRF-валидаторы:

| Раздел | Сериализатор | Поля |
|---|---|---|
| Проекты | `ProjectCreateSerializer`, `ProjectUpdateSerializer` | `title`, `short_desc`, `full_desc`, `location` |
| Вопросы | `QuestionCreateSerializer` | `title`, `description` |
| Ответы | `AnswerCreateSerializer` | `content` |

