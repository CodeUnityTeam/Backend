# Конастанты моделей приложения 'projects'
MIN_LEN_TITLE = 10
MAX_LEN_TITLE = 50
MIN_SHORT_DESC = 20
MAX_SHORT_DESC = 500
MAX_LEN_FULL_DESC = 5000
MAX_LEN_LOCATION = 100
ZERO_SYMBOL = 0
MAX_LEN_STATUS = 20
MAX_LEN_WORK_FORMAT = 50

# Статусы проекта
STATUS_PROJECT = [
    ('draft', 'Черновик'),
    ('published', 'Опубликован'),
    ('recruiting_closed', 'Набор закрыт'),
    ('archived', 'Архив'),
    ('blocked', 'Заблокирован'),
]

# Статусы пользователя в проекте
STATUS_PARTICIPANT = [
    ('author', 'Автор'),
    ('member', 'Участник'),
]
MAX_LEN_STATUS_PARTICIPANT = 20

# Статусы отклика (кто пригласил/сам откликнулся)
INITIATOR_RESPONSE = [
    ('applicant', 'Отклик соискателя'),
    ('author', 'Приглашение от автора'),
]
# Статус отклика пользователя
STATUS_RESPONSE_PROJECT = [
    ('pending', 'Ожидает'),
    ('approved', 'Одобрен'),
    ('rejected', 'Отклонён'),
    ('withdrawn', 'Отозван'),
]
MAX_LEN_INITIATOR_TYPE = 20
MAX_LEN_STATUS_RESPONSE = 20

# Контанты моделей приложения 'qna'
ZERO_LIKE_COUNT = 0
MAX_TITLE_QUESTION = 150
MAX_CONTENT_ANSWER = 2000
MAX_ORIGINAL_NAME = 255
MAX_MINE_TYPE = 100
MAX_IMAGE_URL = 255

# Контанты модели 'specializations'
SPECIALIZATION_NAME_LENGTH = 255

# Контанты модели 'skills'
SKILL_NAME_LENGTH = 255

# Константы приложения 'feedback'
STATUS_FEEDBACK = [
    ('Sent', 'Отправлено'),
    ('In progress', 'В обработке'),
    ('Closed', 'Закрыто'),
]
MAX_LEN_STATUS_FEEDBACK = 50
MAX_CONTENT_FEEDBACK = 1000
MAX_SUBJECT_FEEDBACK = 50

# Константы модели 'users'

MAX_USERNAME_LENGTH = 40
MAX_FIRST_NAME_LENGTH = 35
MAX_LAST_NAME_LENGTH = 64
MAX_EMAIL_LENGTH = 254
MAX_ROLE_LENGTH = 50
ROLE_USER = 'user'
ROLE_MODERATOR = 'moderator'
ROLE_ADMIN = 'admin'
ROLE_CHOICES_LIST = [
    (ROLE_USER, 'Пользователь'),
    (ROLE_MODERATOR, 'Модератор'),
    (ROLE_ADMIN, 'Администратор'),
]
MAX_HASH_LENGTH = 128
