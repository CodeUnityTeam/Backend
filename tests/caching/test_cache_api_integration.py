# ruff: noqa

from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from projects.models import (
    Project,
    ProjectFavorite,
    ProjectLike,
    ProjectParticipant,
)
from projects.views.project import ProjectViewSet
from qna.models import Question, QuestionLike
from qna.views.question import QuestionViewSet
from tests.conftest import UserFactory
from users.models import UserLike
from users.views.profile import UserProfileView


def _request(view, path, *, user=None, **kwargs):
    request = APIRequestFactory().get(path)
    if user is not None:
        force_authenticate(request, user=user)
    response = view(request, **kwargs)
    response.render()
    return response


def _project(author, *, title='Cache integration project'):
    return Project.objects.create(
        author=author,
        title=title,
        short_desc='A sufficiently long description for cache integration.',
        full_desc='Private project details visible to trusted viewers.',
        location='Remote',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        status_project='published',
        published_at=timezone.now(),
    )


def test_public_question_ids_are_shared_but_likes_are_per_viewer():
    author = UserFactory()
    liked_viewer = UserFactory()
    other_viewer = UserFactory()
    question = Question.objects.create(
        user=author,
        title='How are cached question IDs personalized?',
        description='The serialized fields must be calculated for each viewer.',
    )
    QuestionLike.objects.create(user=liked_viewer, question=question)
    cache.clear()

    view = QuestionViewSet.as_view({'get': 'list'})
    anonymous = _request(view, '/api/v1/qna/questions/')
    liked = _request(
        view,
        '/api/v1/qna/questions/',
        user=liked_viewer,
    )
    other = _request(
        view,
        '/api/v1/qna/questions/',
        user=other_viewer,
    )

    assert anonymous.status_code == 200
    assert anonymous.data['items'][0]['is_liked_by_me'] is False
    assert liked.data['items'][0]['is_liked_by_me'] is True
    assert other.data['items'][0]['is_liked_by_me'] is False
    assert len(list(cache.iter_keys('qna:list:ids:public:*'))) == 1


def test_my_question_filter_is_isolated_and_rejected_for_anonymous():
    first_author = UserFactory()
    second_author = UserFactory()
    first_question = Question.objects.create(
        user=first_author,
        title='First author cached question',
        description='This question must only appear in the first my-filter.',
    )
    second_question = Question.objects.create(
        user=second_author,
        title='Second author cached question',
        description='This question must only appear in the second my-filter.',
    )
    cache.clear()

    view = QuestionViewSet.as_view({'get': 'list'})
    first = _request(
        view,
        '/api/v1/qna/questions/?filter=my',
        user=first_author,
    )
    second = _request(
        view,
        '/api/v1/qna/questions/?filter=my',
        user=second_author,
    )
    anonymous = _request(
        view,
        '/api/v1/qna/questions/?filter=my',
    )

    assert [item['question_id'] for item in first.data['items']] == [
        str(first_question.pk),
    ]
    assert [item['question_id'] for item in second.data['items']] == [
        str(second_question.pk),
    ]
    assert anonymous.status_code == 403
    assert len(list(cache.iter_keys('qna:list:ids:*:*'))) == 2


def test_popular_question_order_is_invalidated_after_like(
    django_capture_on_commit_callbacks,
):
    author = UserFactory()
    viewer = UserFactory()
    older = Question.objects.create(
        user=author,
        title='Older question should become popular',
        description='A new like must rebuild the cached popularity ordering.',
    )
    newer = Question.objects.create(
        user=author,
        title='Newer question starts first',
        description='Without likes the model ordering puts this question first.',
    )
    cache.clear()

    view = QuestionViewSet.as_view({'get': 'list'})
    path = '/api/v1/qna/questions/?filter=popular'
    before = _request(view, path, user=viewer)
    list_key = list(cache.iter_keys('qna:list:ids:public:*'))[0]

    assert before.data['items'][0]['question_id'] == str(newer.pk)
    assert cache.get(list_key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        QuestionLike.objects.create(user=viewer, question=older)

    assert cache.get(list_key) is None

    after = _request(view, path, user=viewer)
    assert after.data['items'][0]['question_id'] == str(older.pk)
    assert after.data['items'][0]['likes_count'] == 1


def test_project_favorites_filter_is_personal_for_each_viewer():
    author = UserFactory(projects_relation='employer')
    first_viewer = UserFactory(projects_relation='worker')
    second_viewer = UserFactory(projects_relation='worker')
    first_project = _project(author, title='First favorite project')
    second_project = _project(author, title='Second favorite project')
    ProjectFavorite.objects.create(project=first_project, user=first_viewer)
    ProjectFavorite.objects.create(project=second_project, user=second_viewer)
    cache.clear()

    view = ProjectViewSet.as_view({'get': 'list'})
    path = '/api/v1/projects/?favourites=true'
    first = _request(view, path, user=first_viewer)
    second = _request(view, path, user=second_viewer)
    anonymous = _request(view, path)

    assert [item['project_id'] for item in first.data['items']] == [
        str(first_project.pk),
    ]
    assert [item['project_id'] for item in second.data['items']] == [
        str(second_project.pk),
    ]
    assert anonymous.data['items'] == []
    assert len(list(cache.iter_keys(
        f'projects:list:ids:{first_viewer.pk}:*',
    ))) == 1
    assert len(list(cache.iter_keys(
        f'projects:list:ids:{second_viewer.pk}:*',
    ))) == 1


def test_profile_detail_like_is_per_viewer_and_invalidated_for_actor(
    django_capture_on_commit_callbacks,
):
    worker = UserFactory(projects_relation='worker')
    first_employer = UserFactory(projects_relation='employer')
    second_employer = UserFactory(projects_relation='employer')
    like = UserLike.objects.create(employer=first_employer, worker=worker)
    cache.clear()

    view = UserProfileView.as_view()
    path = f'/api/v1/user/profile/{worker.pk}/'
    first = _request(view, path, user=first_employer, pk=worker.pk)
    second = _request(view, path, user=second_employer, pk=worker.pk)
    first_key = f'users:detail:{worker.pk}:{first_employer.pk}'
    second_key = f'users:detail:{worker.pk}:{second_employer.pk}'

    assert first.data['is_liked'] is True
    assert second.data['is_liked'] is False
    assert cache.get(first_key) is not None
    assert cache.get(second_key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        like.delete()

    assert cache.get(first_key) is None
    assert cache.get(second_key) is not None

    first_after = _request(view, path, user=first_employer, pk=worker.pk)
    assert first_after.data['is_liked'] is False


def test_project_detail_cache_is_personalized_and_like_invalidates_all_viewers(
    django_capture_on_commit_callbacks,
):
    author = UserFactory(projects_relation='employer')
    liked_viewer = UserFactory(projects_relation='worker')
    other_viewer = UserFactory(projects_relation='worker')
    project = _project(author)
    cache.clear()

    view = ProjectViewSet.as_view({'get': 'retrieve'})
    path = f'/api/v1/projects/{project.pk}/'
    liked_before = _request(view, path, user=liked_viewer, project_id=project.pk)
    other_before = _request(view, path, user=other_viewer, project_id=project.pk)
    liked_key = f'projects:detail:{project.pk}:{liked_viewer.pk}'
    other_key = f'projects:detail:{project.pk}:{other_viewer.pk}'
    counter_key = f'counter:project:likes:{project.pk}'

    assert liked_before.data['is_liked_by_me'] is False
    assert other_before.data['is_liked_by_me'] is False
    assert liked_before.data['likes_count'] == 0
    assert cache.get(liked_key) is not None
    assert cache.get(other_key) is not None
    assert cache.get(counter_key) == 0

    with django_capture_on_commit_callbacks(execute=True):
        ProjectLike.objects.create(project=project, user=liked_viewer)

    assert cache.get(liked_key) is None
    assert cache.get(other_key) is None
    assert cache.get(counter_key) is None

    liked_after = _request(view, path, user=liked_viewer, project_id=project.pk)
    other_after = _request(view, path, user=other_viewer, project_id=project.pk)

    assert liked_after.data['is_liked_by_me'] is True
    assert other_after.data['is_liked_by_me'] is False
    assert liked_after.data['likes_count'] == 1
    assert other_after.data['likes_count'] == 1
    assert cache.get(counter_key) == 1


def test_participant_deletion_removes_cached_private_project_fields(
    django_capture_on_commit_callbacks,
):
    author = UserFactory(projects_relation='employer')
    participant = UserFactory(projects_relation='worker')
    project = _project(author, title='Participant invalidation project')
    membership = ProjectParticipant.objects.create(
        project=project,
        user=participant,
        status_participant='member',
    )
    cache.clear()

    view = ProjectViewSet.as_view({'get': 'retrieve'})
    path = f'/api/v1/projects/{project.pk}/'
    before = _request(view, path, user=participant, project_id=project.pk)
    detail_key = f'projects:detail:{project.pk}:{participant.pk}'

    assert before.data['full_desc'] == project.full_desc
    assert before.data['author']['email'] == author.email
    assert cache.get(detail_key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        membership.delete()

    assert cache.get(detail_key) is None

    after = _request(view, path, user=participant, project_id=project.pk)
    assert 'full_desc' not in after.data
    assert 'email' not in after.data['author']
