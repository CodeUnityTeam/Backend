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
    MAX_LEN_FULL_DESC,
    MAX_LEN_LOCATION,
    MAX_LEN_TITLE,
    MAX_PROJECTS_PER_USER,
    MAX_SHORT_DESC,
    MAX_SKILLS_COUNT,
    MIN_LEN_TITLE,
    MIN_SHORT_DESC,
    PUBLISHED,
    RECRUITING_CLOSED,
)

from .models import Project, WorkFormat

User = get_user_model()


# Проверенные валидаторы

def validate_title_project(value: str) -> str:
    """Валидатор для названия проекта."""
    cleaned_value: str = value.strip()
    if not cleaned_value:
        raise serializers.ValidationError(
            'Поле названия проекта не должно быть пустым.',
        )
    if not MIN_LEN_TITLE <= len(cleaned_value) <= MAX_LEN_TITLE:
        raise serializers.ValidationError(
            f'Длина названия проекта должна быть от {MIN_LEN_TITLE} '
            f'до {MAX_LEN_TITLE} символов. Сейчас {len(cleaned_value)}',
        )
    return cleaned_value


def validate_short_desc_project(value: str) -> str:
    """Валидатор для поля 'short_desc' проекта."""
    cleaned_value: str = value.strip()
    if not cleaned_value:
        raise serializers.ValidationError(
            'Поле описания проекта не должно быть пустым.',
        )
    if not MIN_SHORT_DESC <= len(cleaned_value) <= MAX_SHORT_DESC:
        raise serializers.ValidationError(
            f'Описание проекта не может быть короче {MIN_SHORT_DESC} '
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
    """Валидатор для поля 'full_desc' проекта."""
    cleaned_value: str = value.strip()
    if len(cleaned_value) > MAX_LEN_FULL_DESC:
        raise serializers.ValidationError(
            f'Описание проекта не должно превышать {MAX_LEN_FULL_DESC} '
            'символов.',
        )
    return cleaned_value


def validate_location_project(value: str) -> str:
    """Валидатор для местоположения проекта.

    - буквы (A-Za-z, А-Яа-я)
    - цифры (0-9)
    - пробелы
    - дефисы (-)
    """
    cleaned_value = value.strip()
    if len(cleaned_value) > MAX_LEN_LOCATION:
        raise serializers.ValidationError(
            f'Описание проекта не должно превышать {MAX_LEN_FULL_DESC} '
            'символов.',
        )
    if not re.match(r'^[a-zA-Zа-яА-Я0-9\s\-]*$', cleaned_value):
        raise serializers.ValidationError(
            'Локация может содержать '
            'только буквы, цифры, пробелы, дефисы.',
        )
    return cleaned_value

# Непроверенные валидаторы


def extract_relationship_data(validated_data: dict) -> dict:
    """Извлекает данные связей и возвращает их в словаре.

    Забирает уже проверенные объекты из _validated_*,
    которые добавляет validate_project_data.
    Также удаляет оригинальные ключи (skills, specializations,
    project_format), чтобы они не попали в Project.objects.create.
    """
    # Удаляем оригинальные ключи, чтобы не ломать Project.objects.create
    validated_data.pop('skills', None)
    validated_data.pop('specializations', None)
    validated_data.pop('project_format', None)
    return {
        'skills': validated_data.pop('_validated_skills', []),
        'specializations': validated_data.pop(
            '_validated_specializations',
            [],
        ),
        'formats': validated_data.pop('_validated_formats', []),
    }


def add_relationships_to_project(
    project: Project,
    relationship_data: dict,
) -> None:
    """Присваивает связанные объекты проекту после валидации.

    Объекты уже проверены на этапе validate_project_data,
    дополнительные запросы к БД не требуются.
    """
    skills = relationship_data.get('skills', [])
    specializations = relationship_data.get('specializations', [])
    formats = relationship_data.get('formats', [])
    if skills:
        project.skills.set(skills)
    if specializations:
        project.specializations.set(specializations)
    if formats:
        project.project_format.set(formats)


def validate_project_dates(start_date: date, end_date: date) -> None:
    """Валидация дат начала и окончания проекта.

    - Дата начала не может быть раньше текущей даты.
    - Дата окончания не может быть раньше даты начала.
    - Длительность проекта не может превышать 1 год.
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


def validate_project_count(user: User) -> None:
    """Валидация количества проектов у пользователя.

    Проверяет, что у пользователя не больше MAX_PROJECTS_PER_USER
    активных проектов (draft, published, recruiting_closed).
    """
    active_projects_count = Project.objects.filter(
        author=user,
    ).exclude(
        status_project__in=[ARCHIVED, BLOCKED],
    ).count()
    if active_projects_count >= MAX_PROJECTS_PER_USER:
        raise serializers.ValidationError(
            f'У пользователя не может быть больше '
            f'{MAX_PROJECTS_PER_USER} активных проектов. '
            f'Текущее количество: {active_projects_count}.',
        )


def validate_unique_project_title(title: str, user: User) -> None:
    """Проверяет, что у пользователя нет проекта с таким же названием.

    Использует регистронезависимое сравнение (__iexact),
    чтобы 'Проект' и 'проект' считались дубликатами.
    """
    project_model = apps.get_model('projects', 'Project')
    if project_model.objects.filter(
        author=user,
        title__iexact=title,
    ).exists():
        raise serializers.ValidationError({
            'title': 'Проект с таким названием у вас уже существует.',
        })


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
    existing_objects = list(model_class.objects.filter(pk__in=ids))
    existing_ids = {str(obj.pk) for obj in existing_objects}
    missing_ids = set(ids) - existing_ids
    if missing_ids:
        raise serializers.ValidationError(
            f'{error_label.capitalize()} с ID '
            f'{", ".join(missing_ids)} не найден(ы)',
        )
    return existing_objects


def _validate_formats_by_uuid_list(format_ids: list) -> list:
    """Валидация форматов работы, переданных как список UUID."""
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
                f'Формат(ы) работы с ID '
                f'{", ".join(missing_ids)} не найден(ы)'
            ),
        })
    return list(existing_formats)


def validate_create_project_status(status_project: str) -> None:
    """Валидация статуса для создания проекта."""
    if status_project not in (DRAFT, PUBLISHED):
        raise serializers.ValidationError({
            'status_project': (
                f'Статус проекта должен быть "{DRAFT}" или "{PUBLISHED}". '
                f'Получено: "{status_project}".'
            ),
        })


def validate_update_project_status(
    current_status: str,
    new_status: str,
) -> None:
    """Валидация смены статуса проекта при обновлении.

    Разрешённые переходы:
      - draft → published
      - published → recruiting_closed
      - recruiting_closed → published

    Запрещено:
      - draft → recruiting_closed
      - published → draft
      - recruiting_closed → draft
    """
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


def validate_project_data(data: dict, user: User) -> dict:
    """Единая валидация всех данных для создания проекта.

    Проверяет:
    - количество активных проектов у пользователя
      не более MAX_PROJECTS_PER_USER
    - количество навыков (не более MAX_SKILLS_COUNT)
    - существование всех переданных skills, specializations, work formats
    - текстовые поля title, short_desc, full_desc, location
    Возвращает data с добавленными ключами _validated_*,
    содержащими готовые объекты для создания связей.
    """
    # 1. Лимит проектов у автора
    validate_project_count(user)
    # 2. Валидация текстовых полей
    title = data.get('title')
    if title:
        data['title'] = validate_title_project(title)
        validate_unique_project_title(data['title'], user)
    short_desc = data.get('short_desc')
    if short_desc:
        data['short_desc'] = validate_short_desc_project(short_desc)
    full_desc = data.get('full_desc')
    if full_desc:
        data['full_desc'] = validate_full_desc_project(full_desc)
    location = data.get('location')
    if location:
        data['location'] = validate_location_project(location)
    # 3. Количество навыков
    skills_data = data.get('skills', [])
    if skills_data and len(skills_data) > MAX_SKILLS_COUNT:
        raise serializers.ValidationError({
            'skills': (
                f'Количество навыков не должно превышать '
                f'{MAX_SKILLS_COUNT}. Сейчас: {len(skills_data)}.'
            ),
        })
    Skill = apps.get_model('users', 'Skill')
    Specialization = apps.get_model('users', 'Specialization')
    validated_skills = _validate_related_ids(
        skills_data, 'skill_id', Skill, 'навыки',
    )
    validated_specializations = _validate_related_ids(
        data.get('specializations', []),
        'spec_id',
        Specialization,
        'специализации',
    )
    # Форматы приходят как список UUID ["uuid", "uuid"]
    validated_formats = _validate_formats_by_uuid_list(
        data.get('project_format', []),
    )
    data['_validated_skills'] = validated_skills
    data['_validated_specializations'] = validated_specializations
    data['_validated_formats'] = validated_formats
    return data
