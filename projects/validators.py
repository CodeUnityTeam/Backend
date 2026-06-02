import re

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Model
from rest_framework import serializers

from core.constants import ZERO_SYMBOL
from users.models import Skill, Specialization


def validate_location(location: str) -> str:
    """Валидатор для локации проекта (location).

    - буквы (A-Za-z, А-Яа-я)
    - цифры (0-9)
    - пробелы
    - дефисы (-)
    """
    stripped_loc = location.strip()
    if len(stripped_loc) == ZERO_SYMBOL:
        raise ValidationError('Локация не может быть пустым.')
    if not re.match(r'^[a-zA-Zа-яА-Я0-9\s\-]+$', stripped_loc):
        raise ValidationError(
            'Локация может содержать '
            'только буквы, цифры, пробелы, дефисы.',
        )


def validate_dates(start_date: str, end_date: str) -> None:
    """Валидация дат начала и окончания проекта."""
    if start_date and end_date:
        if start_date > end_date:
            raise serializers.ValidationError({
                'end_date': 'Дата начала не может быть позже даты окончания',
            })


def _validate_skills(skills_data: list[dict]) -> list:
    """Валидирует существование навыков и возвращает объекты."""
    if not skills_data:
        return []
    skill_ids = [item.get('skill_id') for item in skills_data]
    if None in skill_ids:
        raise serializers.ValidationError(
            'В данных навыков отсутствует поле "skill_id"',
        )
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
