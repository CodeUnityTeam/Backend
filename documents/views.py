import logging

from django.templatetags.static import static
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.serializers import DocumentOutSerializer

logger = logging.getLogger(__name__)


class DocumentsListView(APIView):
    """Возвращает список PDF-документов (политика, правила и т.д.)."""

    permission_classes = (AllowAny,)

    # Словарь документов: slug -> {title, filename}
    # filename — имя файла в static/documents/
    DOCUMENTS: dict[str, dict[str, str]] = {
        'privacy_policy': {
            'title': 'Политика конфиденциальности',
            'filename': 'Code_Unity_privacy_policy.pdf',
        },
        'platform_rules': {
            'title': 'Правила пользования платформой',
            'filename': 'Code_Unity_platform_rules.pdf',
        },
        'personal_data_processing': {
            'title': 'Обработка персональных данных',
            'filename': 'Code_Unity_personal_data_processing.pdf',
        },
    }

    # Словарь документов: slug -> {title, filename}
    DOCUMENTS_DESCRIPTION: dict[str, str] = {
        'privacy_policy': 'Политика конфиденциал',
    }

    @extend_schema(
        tags=['Documents'],
        summary='Список документов',
        description=(
            'Возвращает список PDF-документов площадки '
            '(политика конфиденциальности, правила и т.д.) '
            'с URL для скачивания.'
        ),
        responses=DocumentOutSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        """Вернуть список документов с автогенерацией file_url."""
        logger.info('Запрос списка документов')

        documents = []
        for slug, info in self.DOCUMENTS.items():
            file_url = request.build_absolute_uri(
                static(f'documents/{info["filename"]}'),
            )
            documents.append({
                'slug': slug,
                'title': info['title'],
                'file_url': file_url,
            })

        serializer = DocumentOutSerializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
