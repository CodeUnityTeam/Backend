from datetime import date
import re

from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.db.models import Model
from rest_framework import serializers

from core.constants import ZERO_SYMBOL, MIN_LEN_TITLE, MAX_LEN_TITLE, MAX_LEN_FULL_DESC, MAX_LEN_LOCATION


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
    if not MIN_LEN_TITLE <= len(cleaned_value) <= MAX_LEN_TITLE:
        raise serializers.ValidationError(
            f'Описание проекта не может быть короче {MIN_LEN_TITLE} '
            f'и более {MAX_LEN_TITLE} символов. '
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


def validate_project_start_date(start_date: date) -> date:
    """Валидация даты начала проекта."""
    current_date = date.today()
    if start_date >= current_date:
        raise serializers.ValidationError(
            'Дата начала проекта не может быть раньше текущей даты '
            f'Сегодня: {current_date}',
        )
    return start_date


def validate_project_end_date(start_date: date, end_date: date) -> date:
    """Валидация даты окончания проекта."""
    if end_date < start_date:
        raise serializers.ValidationError(
            'Дата окончания работ не может быть раньше даты начала проекта',
        )
    max_end_date = start_date + relativedelta(years=1)
    if end_date > max_end_date:
        raise serializers.ValidationError(
            'Дата окончания проекта не может превышать 1 год с начала проекта',
        )
    return end_date


# Непроверенные валидаторы

def _validate_skills(skills_data: list[dict]) -> list:
    """Валидирует существование навыков и возвращает объекты."""
    if not skills_data:
        return []
    skill_ids = [item.get('skill_id') for item in skills_data]
    if None in skill_ids:
        raise serializers.ValidationError(
            'В данных навыков отсутствует поле "skill_id"',
        )
    Skill = apps.get_model('users', 'Skill')
    existing_skills = Skill.objects.filter(skill_id__in=skill_ids)
    existing_ids = {str(skill.skill_id) for skill in existing_skills}
    missing_ids = set(skill_ids) - existing_ids
    if missing_ids:
        raise serializers.ValidationError(
            f'Навык(и) с ID {", ".join(missing_ids)} не найден(ы)',
        )
    return list(existing_skills)


def _validate_specializations(specializations_data: list[dict]) -> list:
    """Валидирует существование специализаций и возвращает объекты."""
    if not specializations_data:
        return []
    spec_ids = [item.get('spec_id') for item in specializations_data]
    if None in spec_ids:
        raise serializers.ValidationError(
            'В данных специализаций отсутствует поле "spec_id"',
        )
    Specialization = apps.get_model('users', 'Specialization')
    existing_specs = Specialization.objects.filter(spec_id__in=spec_ids)
    existing_ids = {str(spec.spec_id) for spec in existing_specs}
    missing_ids = set(spec_ids) - existing_ids
    if missing_ids:
        raise serializers.ValidationError(
            f'Специализация(и) с ID {", ".join(missing_ids)} не найдена(ы)',
        )
    return list(existing_specs)


def _validate_formats(formats_data: list) -> list:
    """Валидирует существование форматов работы и возвращает объекты."""
    if not formats_data:
        return []
    WorkFormat = apps.get_model('projects', 'WorkFormat')
    format_ids_str = [str(uuid_obj) for uuid_obj in formats_data]
    existing_formats = WorkFormat.objects.filter(format_id__in=format_ids_str)
    existing_ids = {str(fmt.format_id) for fmt in existing_formats}
    missing_ids = set(format_ids_str) - existing_ids
    if missing_ids:
        raise serializers.ValidationError({
            'formats': (
                f'Формат(ы) работы с ID '
                f'{", ".join(missing_ids)} не найден(ы)'
            ),
        })
    return list(existing_formats)


def extract_relationship_data(validated_data: dict) -> dict:
    """Извлекает данные связей и возвращает их в словаре."""
    return {
        'skills': validated_data.pop('skills', []),
        'specializations': validated_data.pop('specializations', []),
        'formats': validated_data.pop('project_format', []),
    }


def add_relationships_to_project(
    project: Model,
    relationship_data: dict,
) -> None:
    """Присваивает связанные объекты проекту после валидации."""
    skills = _validate_skills(relationship_data.get('skills', []))
    specializations = _validate_specializations(
        relationship_data.get('specializations', []),
    )
    formats = _validate_formats(relationship_data.get('formats', []))
    if 'skills' in relationship_data and skills:
        project.skills.set(skills)
    if 'specializations' in relationship_data and specializations:
        project.specializations.set(specializations)
    if 'formats' in relationship_data and formats:
        project.project_format.set(formats)
