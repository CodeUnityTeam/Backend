# TODO [QNA-19/19]: Файл core/constants/qna.py не используется.
#   Все импорты констант qna идут из core/constants/__init__.py (строка 43-49),
#   где эти же константы продублированы. При этом в __init__.py нет
#   MAX_TITLE_QUESTION = 150, который определён здесь (строка 3).
#   А модель Question.title (qna/models.py:37) использует MAX_LEN_TITLE = 50
#   из __init__.py, хотя здесь есть MAX_TITLE_QUESTION = 150.
#   Решение:
#   - Либо удалить core/constants/qna.py и перенести MAX_TITLE_QUESTION в __init__
#   - Либо перевести все импорты на core.constants.qna и удалить дубликаты из __init__

# Контанты моделей приложения 'qna'
ZERO_LIKE_COUNT = 0
MAX_TITLE_QUESTION = 150
MAX_CONTENT_ANSWER = 2000
MAX_ORIGINAL_NAME = 255
MAX_MINE_TYPE = 100
MAX_IMAGE_URL = 255
MAX_LEN_TITLE = 50
