# =============================================================================
# Cache timeouts (в секундах)
# =============================================================================

# Справочные данные (Skills, Specializations, WorkFormats)
TAGS_CACHE_TIMEOUT = 60 * 60  # 1 час

# Проекты
PROJECT_LIST_CACHE_TIMEOUT = 60 * 5  # 5 минут
PROJECT_DETAIL_CACHE_TIMEOUT = 60 * 10  # 10 минут
PROJECT_RECOMMENDATIONS_CACHE_TIMEOUT = 60 * 10  # 10 минут

# Q&A
QUESTION_LIST_CACHE_TIMEOUT = 60 * 3  # 3 минуты
QUESTION_DETAIL_CACHE_TIMEOUT = 60 * 5  # 5 минут

# Пользователи
USER_PROFILE_CACHE_TIMEOUT = 60 * 10  # 10 минут
USER_PROFILE_LIST_CACHE_TIMEOUT = 60 * 5  # 5 минут

# Отклики/приглашения
RESPONSE_FEED_CACHE_TIMEOUT = 60 * 3  # 3 минуты

# Отзывы
REVIEW_LIST_CACHE_TIMEOUT = 60 * 3  # 3 минуты
REVIEW_DETAIL_CACHE_TIMEOUT = 60 * 5  # 5 минут

# =============================================================================
# Cache key prefixes
# =============================================================================

CACHE_KEY_PROJECTS_PREFIX = 'projects'
CACHE_KEY_QNA_PREFIX = 'qna'
CACHE_KEY_USERS_PREFIX = 'users'
CACHE_KEY_SKILLS_PREFIX = 'skills'
CACHE_KEY_SPECIALIZATIONS_PREFIX = 'specializations'
CACHE_KEY_WORK_FORMATS_PREFIX = 'work_formats'
CACHE_KEY_RESPONSES_PREFIX = 'responses'
CACHE_KEY_REVIEWS_PREFIX = 'reviews'

# =============================================================================
# Counter prefixes (incr/decr в Redis)
# =============================================================================

COUNTER_PROJECT_LIKES_PREFIX = 'counter:project:likes'
COUNTER_PROJECT_PARTICIPANTS_PREFIX = 'counter:project:participants'
