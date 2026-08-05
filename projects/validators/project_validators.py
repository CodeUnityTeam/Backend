import re
from datetime import date

from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from rest_framework import serializers

from core.constants.projects import (
    ARCHIVED,
    BLOCKED,
    DRAFT,
    MAX_FILTER_DAYS,
    MAX_LEN_FULL_DESC,
    MAX_LEN_LOCATION,
    MAX_LEN_TELEGRAM,
    MAX_LEN_TITLE,
    MAX_PROJECTS_PER_AUTHOR,
    MAX_SHORT_DESC,
    MAX_SKILLS_COUNT,
    MIN_FILTER_DAYS,
    MIN_LEN_TITLE,
    MIN_SHORT_DESC,
    PUBLISHED,
    RECRUITING_CLOSED,
)
from projects.models import Project, WorkFormat

User = get_user_model()


def validate_title_project(
    value: str,
    user: User,
    exclude_project_id: str | None = None,
) -> str:
    """Валидирует название проекта с проверкой на дубликаты пользователя.

    Выполняет следующие проверки:
        1. Удаляет ведущие и завершающие пробелы.
        2. Проверяет длину названия на соответствие допустимому диапазону.
        3. Проверяет отсутствие проекта с таким же названием у текущего
           пользователя (регистронезависимо).

    Особенности:
        - Сравнение выполняется регистронезависимо через `__iexact`,
          поэтому 'МойПроект' и 'мойпроект' считаются дубликатами.
        - Проверка дубликатов выполняется только в рамках одного автора.
        - Если передан exclude_project_id — проект с этим ID исключается
          из проверки (используется при обновлении проекта).
    """
    cleaned_value: str = value.strip()
    if not MIN_LEN_TITLE <= len(cleaned_value) <= MAX_LEN_TITLE:
        raise serializers.ValidationError(
            f'Длина названия проекта должна быть от {MIN_LEN_TITLE} '
            f'до {MAX_LEN_TITLE} символов. Сейчас {len(cleaned_value)}',
        )
    project_model = apps.get_model('projects', 'Project')
    qs = project_model.objects.filter(
        author=user,
        title__iexact=cleaned_value,
    )
    if exclude_project_id is not None:
        qs = qs.exclude(project_id=exclude_project_id)
    if qs.exists():
        raise serializers.ValidationError({
            'title': 'Проект с таким названием у вас уже существует.',
        })
    return cleaned_value


def validate_short_desc_project(value: str) -> str:
    """Валидирует краткое описание проекта.

    Выполняет следующие проверки:
        1. Удаляет ведущие и завершающие пробелы.
        2. Проверяет длину описания на соответствие допустимому диапазону.
        3. Запрещает использование HTML-тегов (символов '<' и '>').
    """
    cleaned_value: str = value.strip()
    if not MIN_SHORT_DESC <= len(cleaned_value) <= MAX_SHORT_DESC:
        raise serializers.ValidationError(
            f'Кратное описание проекта не может быть короче {MIN_SHORT_DESC} '
            f'и более {MAX_SHORT_DESC} символов. '
            f'Текущая длина: {len(cleaned_value)}',
        )

    if re.search(r'<[^>]+>', cleaned_value):
        raise serializers.ValidationError(
            'В кратком описании проекта запрещены HTML-теги: символы "<" и '
            '">". ',
        )
    return cleaned_value


def validate_full_desc_project(value: str) -> str:
    """Валидирует полное описание проекта.

    Выполняет следующие проверки:
        1. Удаляет ведущие и завершающие пробелы.
        2. Проверяет длину описания на превышение максимально допустимого
           значения.
    """
    if value is None:
        return value
    cleaned_value: str = value.strip()
    if len(cleaned_value) > MAX_LEN_FULL_DESC:
        raise serializers.ValidationError(
            f'Полное описание проекта не должно превышать {MAX_LEN_FULL_DESC} '
            'символов.',
        )
    return cleaned_value


def validate_location_project(value: str) -> str:
    """Валидирует местоположение проекта.

    Выполняет следующие проверки:
        1. Удаляет ведущие и завершающие пробелы.
        2. Проверяет длину на превышение максимально допустимого значения.
        3. Проверяет, что строка содержит только разрешённые символы:
        буквы (A-Za-z, А-Яа-я), цифры (0-9), пробелы и дефисы (-).
    """
    if value is None:
        return value
    cleaned_value = value.strip()
    if len(cleaned_value) > MAX_LEN_LOCATION:
        raise serializers.ValidationError(
            f'Местоположение не должно превышать {MAX_LEN_FULL_DESC} '
            'символов.',
        )
    if not re.match(r'^[a-zA-Zа-яА-Я0-9\s\-]*$', cleaned_value):
        raise serializers.ValidationError(
            'Местоположение может содержать '
            'только буквы, цифры, пробелы, дефисы.',
        )
    return cleaned_value


def extract_relationship_data(validated_data: dict) -> dict:
    """Извлекает данные связей и возвращает их в словаре.

    Поведение:
        - Забирает уже проверенные объекты из _validated_*,
        которые добавляет validate_project_data.
        - Удаляет оригинальные ключи (skills, specializations,
        project_format), чтобы они не попали в Project.objects.create.

    Возвращает None для ключей, которые не были переданы
    (чтобы add_relationships_to_project не трогал существующие связи).
    """
    # Удаляем оригинальные ключи, чтобы не ломать Project.objects.create
    validated_data.pop('skills', None)
    validated_data.pop('specializations', None)
    validated_data.pop('project_format', None)
    return {
        'skills': validated_data.pop('_validated_skills', None),
        'specializations': validated_data.pop(
            '_validated_specializations',
            None,
        ),
        'formats': validated_data.pop('_validated_formats', None),
    }


def add_relationships_to_project(
    project: Project,
    relationship_data: dict,
) -> None:
    """Присваивает связанные объекты проекту после валидации.

    Поведение:
        - Если передан пустой список — связи очищаются.
        - Если ключ отсутствует или равен `None` — связи не трогаются.
    """
    skills = relationship_data.get('skills')
    if skills is not None:
        project.skills.set(skills)
    specializations = relationship_data.get('specializations')
    if specializations is not None:
        project.specializations.set(specializations)
    formats = relationship_data.get('formats')
    if formats is not None:
        project.project_format.set(formats)


def validate_project_dates(start_date: date, end_date: date) -> None:
    """Валидирует даты начала и окончания проекта.

    Выполняет следующие проверки:
        1. Дата начала не может быть раньше текущей даты.
        2. Дата окончания не может быть раньше даты начала.
        3. Длительность проекта не может превышать 1 год.
    """
    current_date = date.today()
    if start_date < current_date:
        raise serializers.ValidationError(
            'Дата начала проекта не может быть раньше текущей даты. '
            f'Сегодня: {current_date}',
        )
    if end_date < start_date:
        raise serializers.ValidationError(
            'Дата окончания работ не может быть раньше даты начала проекта.',
        )
    max_end_date = start_date + relativedelta(years=1)
    if end_date > max_end_date:
        raise serializers.ValidationError(
            'Дата окончания проекта не может '
            'превышать 1 год с начала проекта.',
        )


def validate_published_project_dates(
    start_date: date | None,
    end_date: date | None,
    current_start_date: date,
) -> None:
    """Валидирует даты опубликованного проекта.

     Проверки выполняются как для полей 'published', так и для
    'recruiting_closed'.

    Проверки:
        1. Если текущая дата начала уже в прошлом, её нельзя изменить.
        2. Дата окончания не может быть в прошлом.
        3. Дата окончания не может быть раньше даты начала (используется
           новая дата начала, если она передана, иначе текущая).
    """
    current_date = date.today()
    # 1. Защита start_date, если она уже в прошлом
    if start_date is not None and start_date != current_start_date:
        if current_start_date < current_date:
            raise serializers.ValidationError({
                'start_date': (
                    'Дата начала проекта не может быть изменена, '
                    'так как она уже наступила.'
                ),
            })
    # 2. end_date не может быть в прошлом
    if end_date is not None and end_date < current_date:
        raise serializers.ValidationError({
            'end_date': (
                'Дата окончания проекта не может быть раньше текущей даты. '
                f'Сегодня: {current_date}'
            ),
        })
    # 3. end_date не может быть раньше start_date
    effective_start = (
        start_date if start_date is not None else current_start_date
    )
    if end_date is not None and end_date < effective_start:
        raise serializers.ValidationError({
            'end_date': (
                'Дата окончания работ не может быть раньше '
                'даты начала проекта.'
            ),
        })


def validate_duration_project(
    duration_min: int | None,
    duration_max: int | None,
) -> None:
    """Валидация продолжительности дней в фильтре для списка проектов."""
    for value in (duration_min, duration_max):
        if value is None:
            continue
        if (
            not isinstance(value, int)
            or not MIN_FILTER_DAYS <= value <= MAX_FILTER_DAYS
        ):
            raise serializers.ValidationError(
                'Параметры duration_min и duration_max должны быть целыми '
                f'числами от {MIN_FILTER_DAYS} до {MAX_FILTER_DAYS}.',
            )


def validate_project_count_per_author(user: User) -> None:
    """Валидация количества проектов у автора.

    Проверяет, что у пользователя не больше MAX_PROJECTS_PER_AUTHOR
    активных проектов (draft, published, recruiting_closed).
    """
    active_projects_count = (
        Project.objects
        .filter(
            author=user,
        )
        .exclude(
            status_project__in=[ARCHIVED, BLOCKED],
        )
        .count()
    )
    if active_projects_count >= MAX_PROJECTS_PER_AUTHOR:
        raise serializers.ValidationError(
            f'У пользователя не может быть больше '
            f'{MAX_PROJECTS_PER_AUTHOR} активных проектов. '
            f'Текущее количество: {active_projects_count}.',
        )


def _validate_related_ids(
    data_items: list,
    id_field: str,
    model_class: type[Model],
    error_label: str,
) -> list:
    """Универсальная валидация существования связанных объектов.

    Принимает список словарей с ID, извлекает ID по id_field,
    проверяет их существование в БД.

    Возвращает список найденных объектов.
    """
    if not data_items:
        return []
    ids = [item.get(id_field) for item in data_items]
    if None in ids:
        raise serializers.ValidationError(
            f'В данных {error_label} отсутствует поле "{id_field}"',
        )
    ids_str = [str(obj_id) for obj_id in ids]
    existing_objects = list(model_class.objects.filter(pk__in=ids))
    existing_ids = {str(obj.pk) for obj in existing_objects}
    missing_ids = set(ids_str) - existing_ids
    if missing_ids:
        raise serializers.ValidationError(
            f'{error_label.capitalize()} с ID '
            f'{", ".join(missing_ids)} не найден(ы)',
        )
    return existing_objects


def _validate_formats_by_uuid_list(format_ids: list) -> list:
    """Валидирует форматы работы, переданные как список UUID.

    Возвращает список найденных объектов WorkFormat.
    """
    if not format_ids:
        return []
    format_ids_str = [str(uuid_obj) for uuid_obj in format_ids]
    existing_formats = WorkFormat.objects.filter(
        format_id__in=format_ids_str,
    )
    existing_ids = {str(fmt.format_id) for fmt in existing_formats}
    missing_ids = set(format_ids_str) - existing_ids
    if missing_ids:
        raise serializers.ValidationError({
            'project_format': (
                f'Формат(ы) работы с ID {", ".join(missing_ids)} не найден(ы)'
            ),
        })
    return list(existing_formats)


def validate_create_project_status(status_project: str) -> None:
    """Валидирует статус проекта при создании.

    При создании проекта допустимы только статусы DRAFT и PUBLISHED.
    """
    if status_project not in (DRAFT, PUBLISHED):
        raise serializers.ValidationError({
            'status_project': (
                f'Статус проекта должен быть "{DRAFT}" или "{PUBLISHED}". '
                f'Получено: "{status_project}".'
            ),
        })


def validate_telegram_contact(value: str) -> str:
    """Валидирует Telegram-контакт.

    Проверки:
        1. Если пустая строка — пропускаем.
        2. Длина не более MAX_LEN_TELEGRAM.
        3. Формат: @username (только латиница, цифры, подчёркивание).
    """
    if not value:
        return value
    cleaned_value = value.strip()
    if len(cleaned_value) > MAX_LEN_TELEGRAM:
        raise serializers.ValidationError(
            f'Telegram-контакт не должен превышать '
            f'{MAX_LEN_TELEGRAM} символов. Сейчас: {len(cleaned_value)}.',
        )
    if not re.match(r'^@[a-zA-Z0-9_]+$', cleaned_value):
        raise serializers.ValidationError(
            'Telegram-контакт должен начинаться с @ и содержать '
            'только латинские буквы, цифры и подчёркивание.',
        )
    return cleaned_value


def validate_update_project_status(
    current_status: str,
    new_status: str,
) -> None:
    """Валидация смены статуса проекта при обновлении.

    Если статус не меняется — валидация пропускается.

    Разрешённые переходы:
      - draft → published
      - published → recruiting_closed
      - recruiting_closed → published

    Запрещено:
      - draft → recruiting_closed
      - published → draft
      - recruiting_closed → draft
    """
    if current_status == new_status:
        return
    allowed_transitions = {
        DRAFT: (PUBLISHED,),
        PUBLISHED: (RECRUITING_CLOSED,),
        RECRUITING_CLOSED: (PUBLISHED,),
    }
    allowed = allowed_transitions.get(current_status, ())
    if new_status not in allowed:
        raise serializers.ValidationError({
            'status_project': (
                f'Переход из статуса "{current_status}" '
                f'в статус "{new_status}" запрещён.'
            ),
        })


def validate_project_data(
    data: dict,
    user: User,
    exclude_project_id: str | None = None,
) -> dict:
    """Единая валидация всех данных для создания/обновления проекта.

    Проверяет:
        1. Количество активных проектов у пользователя
           (не более MAX_PROJECTS_PER_USER).
        2. Текстовые поля: title, short_desc, full_desc, location.
        3. Наличие и количество навыков (не более MAX_SKILLS_COUNT).
        4. Существование всех переданных skills, specializations, work formats.

    Args:
        data: Словарь с данными проекта.
        user: Пользователь — автор проекта.
        exclude_project_id: ID проекта, который нужно исключить из проверки
            на дубликат названия (используется при обновлении).

    Возвращает:
        Словарь data с добавленными ключами:
            - _validated_skills: список объектов Skill
            - _validated_specializations: список объектов Specialization
            - _validated_formats: список объектов WorkFormat

    """
    # Валидиция лимита проектов у автора
    validate_project_count_per_author(user)
    # Валидация текстовых полей
    data['title'] = validate_title_project(
        data['title'], user, exclude_project_id=exclude_project_id,
    )
    data['short_desc'] = validate_short_desc_project(data['short_desc'])
    data['full_desc'] = validate_full_desc_project(data['full_desc'])
    data['location'] = validate_location_project(data['location'])
    data['telegram_contact'] = validate_telegram_contact(
        data.get('telegram_contact'),
    )
    # Валидация навыков
    skills_data = data.get('skills', [])
    if not skills_data:
        raise serializers.ValidationError({
            'skills': 'Необходимо указать хотя бы один навык.',
        })
    if len(skills_data) > MAX_SKILLS_COUNT:
        raise serializers.ValidationError({
            'skills': (
                f'Количество навыков не должно превышать '
                f'{MAX_SKILLS_COUNT}. Сейчас: {len(skills_data)}.'
            ),
        })
    Skill = apps.get_model('users', 'Skill')
    Specialization = apps.get_model('users', 'Specialization')
    validated_skills = _validate_related_ids(
        skills_data,
        'skill_id',
        Skill,
        'навыки',
    )
    # Валидация специализаций
    specializations_data = data.get('specializations', [])
    if not specializations_data:
        raise serializers.ValidationError({
            'specializations': (
                'Необходимо указать хотя бы одну специализацию.',
            ),
        })
    validated_specializations = _validate_related_ids(
        specializations_data,
        'spec_id',
        Specialization,
        'специализации',
    )
    # Валидация форматов работы (список UUID)
    validated_formats = _validate_formats_by_uuid_list(
        data.get('project_format', []),
    )
    # Сохранение проверенных объектов для последующего использования
    data['_validated_skills'] = validated_skills
    data['_validated_specializations'] = validated_specializations
    data['_validated_formats'] = validated_formats
    return data
