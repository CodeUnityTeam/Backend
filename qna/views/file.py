from django.core.files.uploadedfile import UploadedFile
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from qna.serializers.file import (
    FileUploadResponseSerializer,
    FileUploadSerializer,
)
from qna.services import image_upload_handler


@extend_schema(
    tags=['Files'],
    summary='Загрузить файл',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'string',
                    'format': 'binary',
                },
            },
            'required': ['file'],
        },
    },
    responses=FileUploadResponseSerializer,
)
class FileUploadView(APIView):
    """API view для загрузки изображений в MinIO."""

    parser_classes: list[type[MultiPartParser]] = [MultiPartParser]

    def post(
        self,
        request: Request,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> Response:
        """Загружает файл в MinIO и возвращает публичный URL и метаданные."""
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file: UploadedFile = serializer.validated_data['file']
        public_url: str = image_upload_handler(file_obj=file)

        return Response(
            {
                'image_url': public_url,
                'original_name': file.name,
                'file_size': file.size,
                'mime_type': file.content_type or 'image/jpeg',
            },
            status=status.HTTP_201_CREATED,
        )
