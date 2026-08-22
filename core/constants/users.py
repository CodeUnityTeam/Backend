# --- User model ---
USER_ADDITIONAL_CONTACT_LENGTH = 50
USER_COUNTRY_LENGTH = 70
USER_CITY_LENGTH = 100
USER_EMAIL_LENGTH = 254
USER_ROLE_LENGTH = 20
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 20
PHONE_PATTERN = r'^\+\d{10,20}$'
MAX_CHAR_FIELD_LENGTH = 127

# --- Users validation ---
PASSWORD_MAX_LENGTH = 128
PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = r'^[A-Za-z0-9!"#$%&\'()*+,./:;<=>?@[\\\]^_`{|}~-]+$'
USER_FIRST_NAME_LENGTH = 35
USER_LAST_NAME_LENGTH = 64
# Латиница, кириллица (с Ёё), пробелы и дефисы
USER_NAME_CLEANING_PATTERN = r'[^A-Za-zА-Яа-яЁё\s-]'
USER_NAME_VALIDATION_PATTERN = r'^[A-Za-zА-Яа-яЁё\s-]+$'

# --- Specialization ---
SPECIALIZATION_NAME_LENGTH = 50

# --- Skill ---
SKILL_NAME_LENGTH = 50

# --- Help texts для моделей приложения users ---
USER_EMAIL_HELP = (
    'Действующий и уникальный адрес электронной почты, используемый для входа.'
)
USER_NAME_HELP = 'Допускаются только буквы кириллицы или латиницы.'

# --- UpdateLastActivityMiddleware ---
LAST_LOGIN_UPDATE_INTERVAL = 5
MSG_SUCCESS = 'Письмо с подтверждением успешно отправлено на ваш email.'
MSG_RESENT = (
    'Письмо с подтверждением успешно отправлено на ваш email повторно.'
)

# --- Константы сообщений об ошибках ---
INVALID_FIELD_ERROR = 'Недопустимое значение поля'
INVALID_PASSWORD_ERROR = 'Недопустимое значение пароля'
