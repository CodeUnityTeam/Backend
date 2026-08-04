# ruff: noqa

from datetime import date

from django.core.cache import cache

from core.cache_mixins import get_or_seed_counter
from core.constants.cache import (
    COUNTER_PROJECT_LIKES_PREFIX,
    COUNTER_PROJECT_PARTICIPANTS_PREFIX,
)
from projects.models import (
    ProjectFavorite,
    ProjectLike,
    ProjectParticipant,
    Response,
)
from qna.models import Answer
from users.models import Skill, UserExperience


def _seed(*keys: str) -> None:
    for key in keys:
        cache.set(key, 'cached')


def _assert_deleted(*keys: str) -> None:
    assert cache.get_many(keys) == {}


def test_project_save_invalidates_all_project_representations_after_commit(
    published_project,
    django_capture_on_commit_callbacks,
):
    project_id = published_project.pk
    keys = (
        f'projects:detail:{project_id}:viewer-a',
        'projects:list:ids:viewer-a:filters',
        'projects:recommendations:viewer-a:ids:filters',
        f'{COUNTER_PROJECT_LIKES_PREFIX}:{project_id}',
        f'{COUNTER_PROJECT_PARTICIPANTS_PREFIX}:{project_id}',
    )
    _seed(*keys)

    with django_capture_on_commit_callbacks(execute=True):
        published_project.title = 'Changed caching test project'
        published_project.save(update_fields=['title'])
        assert cache.get_many(keys) == {key: 'cached' for key in keys}

    _assert_deleted(*keys)


def test_project_like_invalidates_count_detail_and_sorted_lists(
    published_project,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    project_id = published_project.pk
    deleted_keys = (
        f'{COUNTER_PROJECT_LIKES_PREFIX}:{project_id}',
        f'projects:detail:{project_id}:{unverified_user.pk}',
        f'projects:list:ids:{unverified_user.pk}:likes-order',
    )
    recommendation_key = (
        f'projects:recommendations:{unverified_user.pk}:ids:stable'
    )
    _seed(*deleted_keys, recommendation_key)

    with django_capture_on_commit_callbacks(execute=True):
        ProjectLike.objects.create(
            project=published_project,
            user=unverified_user,
        )

    _assert_deleted(*deleted_keys)
    assert cache.get(recommendation_key) == 'cached'


def test_favorite_invalidation_is_limited_to_the_acting_viewer(
    published_project,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    project_id = published_project.pk
    actor_detail = f'projects:detail:{project_id}:{unverified_user.pk}'
    other_detail = f'projects:detail:{project_id}:another-viewer'
    actor_list = f'projects:list:ids:{unverified_user.pk}:favorites'
    other_list = 'projects:list:ids:another-viewer:favorites'
    _seed(actor_detail, other_detail, actor_list, other_list)

    with django_capture_on_commit_callbacks(execute=True):
        ProjectFavorite.objects.create(
            project=published_project,
            user=unverified_user,
        )

    _assert_deleted(actor_detail, actor_list)
    assert cache.get(other_detail) == 'cached'
    assert cache.get(other_list) == 'cached'


def test_participant_invalidates_membership_dependent_keys(
    published_project,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    project_id = published_project.pk
    keys = (
        f'{COUNTER_PROJECT_PARTICIPANTS_PREFIX}:{project_id}',
        f'projects:detail:{project_id}:any-viewer',
        f'projects:list:ids:{unverified_user.pk}:membership',
        f'projects:recommendations:{unverified_user.pk}:ids:membership',
    )
    _seed(*keys)

    with django_capture_on_commit_callbacks(execute=True):
        ProjectParticipant.objects.create(
            project=published_project,
            user=unverified_user,
            status_participant='member',
        )

    _assert_deleted(*keys)


def test_response_invalidates_feed_employer_list_and_project_detail(
    published_project,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    keys = (
        f'responses:feed:{unverified_user.pk}:ids:pending',
        f'users:list:ids:{published_project.author_id}:responses',
        f'projects:detail:{published_project.pk}:any-viewer',
    )
    _seed(*keys)

    with django_capture_on_commit_callbacks(execute=True):
        Response.objects.create(
            project=published_project,
            user=unverified_user,
            initiator_type='applicant',
        )

    _assert_deleted(*keys)


def test_answer_invalidates_question_detail_and_membership_lists(
    question,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    keys = (
        f'qna:detail:{question.pk}:viewer',
        'qna:list:ids:public:no-answers',
    )
    _seed(*keys)

    with django_capture_on_commit_callbacks(execute=True):
        Answer.objects.create(
            question=question,
            user=unverified_user,
            content='An answer changes both detail and no-answers filters.',
        )

    _assert_deleted(*keys)


def test_user_experience_invalidates_profile_detail_only(
    verified_user,
    django_capture_on_commit_callbacks,
):
    detail_key = f'users:detail:{verified_user.pk}:viewer'
    list_key = f'users:list:ids:{verified_user.pk}:filters'
    _seed(detail_key, list_key)

    with django_capture_on_commit_callbacks(execute=True):
        UserExperience.objects.create(
            user=verified_user,
            company='Cache Inc.',
            position='Developer',
            responsibilities='Testing invalidation.',
            start_date=date(2024, 1, 1),
        )

    _assert_deleted(detail_key)
    assert cache.get(list_key) == 'cached'


def test_viewer_context_change_invalidates_personal_detail_caches(
    verified_user,
    django_capture_on_commit_callbacks,
):
    viewer_id = verified_user.pk
    keys = (
        f'projects:detail:project-a:{viewer_id}',
        f'users:detail:target-a:{viewer_id}',
        f'projects:list:ids:{viewer_id}:my-projects',
    )
    unaffected = 'projects:detail:project-a:another-viewer'
    _seed(*keys, unaffected)

    with django_capture_on_commit_callbacks(execute=True):
        verified_user.projects_relation = 'employer'
        verified_user.save(update_fields=['projects_relation'])

    _assert_deleted(*keys)
    assert cache.get(unaffected) == 'cached'


def test_skill_change_invalidates_reference_and_all_dependent_views(
    django_capture_on_commit_callbacks,
):
    keys = (
        'skills:list',
        'users:detail:user:viewer',
        'users:list:ids:viewer:skills',
        'projects:detail:project:viewer',
        'projects:list:ids:viewer:skills',
        'projects:recommendations:viewer:ids:skills',
        'qna:detail:question:viewer',
        'qna:list:ids:public:skills',
    )
    _seed(*keys)

    with django_capture_on_commit_callbacks(execute=True):
        Skill.objects.create(name='cache-test-skill')

    _assert_deleted(*keys)


def test_counter_is_reseeded_from_database_after_like_invalidation(
    published_project,
    unverified_user,
    django_capture_on_commit_callbacks,
):
    project_id = str(published_project.pk)
    queryset = ProjectLike.objects.filter(project=published_project)

    assert get_or_seed_counter(
        COUNTER_PROJECT_LIKES_PREFIX,
        project_id,
        queryset,
    ) == 0

    with django_capture_on_commit_callbacks(execute=True):
        ProjectLike.objects.create(
            project=published_project,
            user=unverified_user,
        )

    assert get_or_seed_counter(
        COUNTER_PROJECT_LIKES_PREFIX,
        project_id,
        queryset,
    ) == 1
