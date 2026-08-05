# ruff: noqa

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from projects.models import Project
from qna.models import Question


@pytest.fixture(autouse=True)
def clear_redis_cache() -> Generator[None, None, None]:
    """Keep cache state isolated while still testing the real Redis backend."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def published_project(verified_user):
    return Project.objects.create(
        author=verified_user,
        title='Caching test project',
        short_desc='A sufficiently long project summary for cache tests.',
        full_desc='Project details used by the caching test suite.',
        location='Remote',
        end_date=date.today() + timedelta(days=30),
        status_project='published',
        published_at=timezone.now(),
    )


@pytest.fixture
def question(verified_user):
    return Question.objects.create(
        user=verified_user,
        title='How should application caching be tested?',
        description='A sufficiently detailed question used by cache tests.',
    )
