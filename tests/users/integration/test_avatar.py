from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model
from django.urls import reverse
from pytest_mock import MockerFixture
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
AVATAR_URL = reverse('users:user-avatar')


def test_upload_avatar_successful(
    api_client: APIClient,
    verified_user: Model,
    test_image_file: SimpleUploadedFile,
    mocker: MockerFixture,
) -> None:
    """Успешная первичная загрузка аватара пользователя.

    Проверяет статус ответа 201 Created, обновление поля в СУБД
    и возврат сгенерированного S3 URL-адреса.
    """
    api_client.force_authenticate(user=verified_user)

    fake_s3_url = 'https://codeunity.ru'
    # Патчим S3Service там, где его используют функции в users/services.py
    mocker.patch(
        'minio.s3_utils.S3Service.upload', return_value=fake_s3_url,
    )

    payload = {'file': test_image_file}
    response: Any = api_client.post(
        AVATAR_URL, data=payload, format='multipart',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data == {'avatar_url': fake_s3_url}

    verified_user.refresh_from_db()
    assert getattr(verified_user, 'avatar_url') == fake_s3_url


def test_upload_avatar_overwrites_existing(
    api_client: APIClient,
    verified_user: Model,
    test_image_file: SimpleUploadedFile,
    mocker: MockerFixture,
) -> None:
    """Успешная перезапись существующего аватара пользователя.

    Проверяет, что при загрузке нового изображения старый URL-адрес
    заменяется на новый, а логика удаления старого файла срабатывает.
    """
    api_client.force_authenticate(user=verified_user)

    old_s3_url = 'https://codeunity.ru'
    setattr(verified_user, 'avatar_url', old_s3_url)
    verified_user.save(update_fields=('avatar_url',))

    new_s3_url = 'https://codeunity.ru'
    mocker.patch('minio.s3_utils.S3Service.upload', return_value=new_s3_url)
    mocker.patch('minio.s3_utils.S3Service.delete', return_value=None)

    payload = {'file': test_image_file}
    response: Any = api_client.post(
        AVATAR_URL, data=payload, format='multipart',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data == {'avatar_url': new_s3_url}

    verified_user.refresh_from_db()
    assert getattr(verified_user, 'avatar_url') == new_s3_url


def test_delete_avatar_successful(
    api_client: APIClient, verified_user: Model, mocker: MockerFixture,
) -> None:
    """Успешное удаление текущего аватара соискателя.

    Проверяет статус 204 No Content и очистку поля в базе данных.
    """
    api_client.force_authenticate(user=verified_user)

    setattr(verified_user, 'avatar_url', 'https://minio.ru')
    verified_user.save(update_fields=('avatar_url',))

    mocker.patch('minio.s3_utils.S3Service.delete', return_value=None)

    response: Any = api_client.delete(AVATAR_URL)

    assert response.status_code == status.HTTP_204_NO_CONTENT

    verified_user.refresh_from_db()
    assert getattr(verified_user, 'avatar_url') == ''


def test_delete_avatar_fails_if_already_missing(
    api_client: APIClient, verified_user: Model,
) -> None:
    """Запрет удаления аватара при его фактическом отсутствии.

    Ожидает ошибку 400 Bad Request с соответствующим бизнес-сообщением.
    """
    api_client.force_authenticate(user=verified_user)

    setattr(verified_user, 'avatar_url', '')
    verified_user.save(update_fields=('avatar_url',))

    response: Any = api_client.delete(AVATAR_URL)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'detail': 'Аватар отсутствует.'}
