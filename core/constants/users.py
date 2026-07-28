# --- Users ---
USER_ROLE_LENGTH = 20
USER_FIRST_NAME_LENGTH = 35
USER_LAST_NAME_LENGTH = 64
USER_NAME_PATTERN = r'^[A-Za-zА-Яа-яЁё]+$'
USER_ADDITIONAL_CONTACT_LENGTH = 50
USER_COUNTRY_LENGTH = 70
USER_CITY_LENGTH = 100
USER_EMAIL_LENGTH = 254

MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 20
PHONE_PATTERN = r'^\+\d{10,20}$'
MAX_CHAR_FIELD_LENGTH = 127


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
