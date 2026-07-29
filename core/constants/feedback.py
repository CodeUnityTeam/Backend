# Константы приложения 'feedback'
STATUS_FEEDBACK = (
    ('Sent', 'Отправлено'),
    ('In progress', 'В обработке'),
    ('Closed', 'Закрыто'),
)

FEEDBACK_STATUS_SENT = 'Sent'
FEEDBACK_STATUS_IN_PROGRESS = 'In progress'
FEEDBACK_STATUS_CLOSED = 'Closed'

MAX_LEN_STATUS_FEEDBACK = 50
MAX_CONTENT_FEEDBACK = 1000
MAX_SUBJECT_FEEDBACK = 50
MAX_IMAGE_SIZE_FEEDBACK = 5242880
MAX_IMAGE_COUNT_FEEDBACK = 5

# Константы для модели Review (Отзыв)
MAX_REVIEW_TEXT = 2000
MIN_REVIEW_TEXT = 10
