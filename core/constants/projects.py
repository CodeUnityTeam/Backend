# Конастанты моделей приложения 'projects'
MIN_LEN_TITLE = 10
MAX_LEN_TITLE = 50
MIN_SHORT_DESC = 20
MAX_SHORT_DESC = 500
MIN_LEN_FULL_DESC = 20
MAX_LEN_FULL_DESC = 5000
MAX_LEN_LOCATION = 100
MAX_LEN_TELEGRAM = 50
ZERO_SYMBOL = 0
MAX_LEN_STATUS = 20
MAX_LEN_WORK_FORMAT = 50

DRAFT = 'draft'
PUBLISHED = 'published'
RECRUITING_CLOSED = 'recruiting_closed'
ARCHIVED = 'archived'
BLOCKED = 'blocked'
# Статусы проекта
STATUS_PROJECT = (
    (DRAFT, 'Черновик'),
    (PUBLISHED, 'Опубликован'),
    (RECRUITING_CLOSED, 'Набор закрыт'),
    (ARCHIVED, 'Архив'),
    (BLOCKED, 'Заблокирован'),
)
AUTHOR = 'author'
MEMBER = 'member'
# Статусы пользователя в проекте
STATUS_PARTICIPANT = (
    (AUTHOR, 'Автор'),
    (MEMBER, 'Участник'),
)
MAX_LEN_STATUS_PARTICIPANT = 20
APPLICANT = 'applicant'

# Статусы отклика (кто пригласил/сам откликнулся)
INITIATOR_RESPONSE = (
    (APPLICANT, 'Отклик соискателя'),
    (AUTHOR, 'Приглашение от автора'),
)

PENDING = 'pending'
APPROVED = 'approved'
REJECTED = 'rejected'
WITHDRAWN = 'withdrawn'
# Статус отклика пользователя
STATUS_RESPONSE_PROJECT = (
    (PENDING, 'Ожидает'),
    (APPROVED, 'Одобрен'),
    (REJECTED, 'Отклонён'),
    (WITHDRAWN, 'Отозван'),
)
MAX_LEN_INITIATOR_TYPE = 20
MAX_LEN_STATUS_RESPONSE = 20

# Минимальное количество дней для фильтрации проектов
MIN_FILTER_DAYS = 7
# Максимальное количество дней для фильтрации проектов
MAX_FILTER_DAYS = 365

# Максимальная длина поискового запроса
MAX_SEARCH_LENGTH = 100


PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
PAGE_SIZE_QUERY_PARAM = 'page_size'

ALLOWED_STATUSED_FOR_LIKE = (PUBLISHED, RECRUITING_CLOSED)

# Максимальное количество навыков в проекте
MAX_SKILLS_COUNT = 10
# Максимальное количество специализаций в проекте
MAX_SPECIALIZATIONS_COUNT = 10
# Максимальное количество проектов у пользователя
MAX_PROJECTS_PER_AUTHOR = 10
# Максимальное количество проектов у пользователя - где он участник.
MAX_PROJECTS_PER_MEMBER = 3
