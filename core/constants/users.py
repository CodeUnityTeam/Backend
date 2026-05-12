# --- OauthProvider ---
OAUTHPROVIDER_NAME_LENGTH = 20
DEFAULT_AUTH_PROVIDER_NAME = 'email'

# --- Users ---
USER_GROUP_NAME = 'user'
MODERATOR_GROUP_NAME = 'moderator'
ADMIN_GROUP_NAME = 'admin'
DEFAULT_GROUP_NAMES = (
    USER_GROUP_NAME,
    MODERATOR_GROUP_NAME,
    ADMIN_GROUP_NAME,
)
USER_ROLE_LENGTH = 20
USER_NAME_LENGTH = 35
USER_SURNAME_LENGTH = 64
USER_ADDITIONAL_CONTACT_LENGTH = 50
USER_COUNTRY_LENGTH = 70
USER_CITY_LENGTH = 100
USER_NAME_MIN_LENGTH = USER_SURNAME_MIN_LENGTH = 2
USER_NAME_PATTERN = r'^[A-Za-zА-Яа-яЁё]+$'
USER_EMAIL_LENGTH = 254

MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 20
PHONE_PATTERN = rf'^\+\d{{{MIN_PHONE_DIGITS},{MAX_PHONE_DIGITS}}}$'


# --- Specialization ---
SPECIALIZATION_NAME_LENGTH = 50

# --- Skill ---
SKILL_NAME_LENGTH = 50


# --- Help texts для моделей приложения users ---
USER_EMAIL_HELP = (
    'Действующий и уникальный адрес электронной почты, используемый для входа.'
)
USER_NAME_HELP = 'Введите имя (только буквы кириллицы или латиницы).'
USER_SURNAME_HELP = 'Введите фамилию (только буквы кириллицы или латиницы).'
