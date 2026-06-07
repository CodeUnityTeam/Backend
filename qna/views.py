from django.core.files.uploadedfile import UploadedFile
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin, ListModelMixin
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from qna.models import (
    Answer,
    AnswerLike,
    Question,
    QuestionLike,
)
from qna.serializers import (
    AnswerCreateResponseSerializer,
    AnswerCreateSerializer,
    AnswerDetailSerializer,
    FileUploadResponseSerializer,
    FileUploadSerializer,
    LikeSerializer,
    QuestionCreateResponseSerializer,
    QuestionCreateSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
    SkillSerializer,
)
from qna.services import image_upload_handler
from users.models import Skill


@extend_schema_view(
    list=extend_schema(tags=['Questions'], summary='Список вопросов'),
    create=extend_schema(tags=['Questions'], summary='Создать вопрос'),
    retrieve=extend_schema(
        tags=['Questions'],
        summary='Детальная страница вопроса',
    ),
    partial_update=extend_schema(
        tags=['Questions'],
        summary='Редактировать вопрос',
    ),
    destroy=extend_schema(tags=['Questions'], summary='Удалить вопрос'),
)
class QuestionViewSet(viewsets.ModelViewSet):
    """Представление для вопросов."""

    queryset = Question.objects.all()
    serializer_class = QuestionCreateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self) -> type[serializers.BaseSerializer]:
        """Получает класс сериализатора."""
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'retrieve':
            return QuestionDetailSerializer
        return QuestionCreateSerializer

    @extend_schema(
        responses=inline_serializer(
            name='QuestionRetrieveResponse',
            fields={
                'question': QuestionDetailSerializer(),
                'answers': AnswerDetailSerializer(many=True),
            },
        ),
    )
    def retrieve(
        self,
        request: Request,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> Response:
        """Возвращает детальную страницу вопроса."""
        question = self.get_object()
        answers = question.answers.filter(is_active=True)
        return Response({
            'question': QuestionDetailSerializer(question).data,
            'answers': AnswerDetailSerializer(answers, many=True).data,
        })

    @extend_schema(
            request=QuestionCreateSerializer,
            responses=QuestionCreateResponseSerializer,
        )
    def create(self, request: Request) -> Response:
        """Создаёт вопрос."""
        serializer = QuestionCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(
            QuestionCreateResponseSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=QuestionCreateSerializer,
        responses=QuestionCreateResponseSerializer,
    )
    def partial_update(
        self,
        request: Request,
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> Response:
        """Обновляет вопрос частично."""
        question = self.get_object()
        serializer = QuestionCreateSerializer(
            question,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(
            QuestionCreateResponseSerializer(question).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AnswerCreateSerializer,
        responses=AnswerCreateResponseSerializer,
        tags=['Answers'],
        summary='Создать ответ',
    )
    @action(detail=True, methods=['post'], url_path='answers')
    def add_answer(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Создаёт ответ на вопрос."""
        question = self.get_object()
        serializer = AnswerCreateSerializer(
            data=request.data,
            context={'request': request, 'question': question},
        )
        serializer.is_valid(raise_exception=True)
        answer = serializer.save()
        return Response(
            AnswerCreateResponseSerializer(answer).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=['Likes'],
        summary='Лайк/снятие лайка вопроса',
        request=None,
        responses=LikeSerializer(),
    )
    @action(detail=True, methods=['post'], url_path='like')
    def like(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Ставит или снимает лайк на вопрос."""
        question = self.get_object()
        user = request.user
        like, created = QuestionLike.objects.get_or_create(
            question=question,
            user=user,
        )
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({
            'liked': liked,
            'likes_count': question.likes.count(),
        })


@extend_schema_view(
    destroy=extend_schema(tags=['Answers'], summary='Удалить ответ'),
    like=extend_schema(
        tags=['Likes'],
        summary='Лайк/снятие лайка ответа',
        request=None,
        responses=LikeSerializer(),
    ),
)
class AnswerViewSet(DestroyModelMixin, GenericViewSet):
    """Представление для ответов."""

    queryset = Answer.objects.all()
    serializer_class = AnswerDetailSerializer

    @extend_schema(
            tags=['Answers'],
            summary='Лайк/снятие лайка ответа',
        )
    @action(detail=True, methods=['post'], url_path='like')
    def like(
        self,
        request: Request,
        *args,  # noqa ANN:002
        **kwargs  # noqa ANN:003
    ) -> Response:
        """Ставит или снимает лайк на ответ."""
        answer = self.get_object()
        user = request.user
        like, created = AnswerLike.objects.get_or_create(
            answer=answer,
            user=user,
        )
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({
            'liked': liked,
            'likes_count': answer.likes.count(),
        })


@extend_schema_view(
    list=extend_schema(tags=['Tags'], summary='Список тегов (скиллов)'),
)
class SkillViewSet(ListModelMixin, GenericViewSet):
    """Представление для Тегов (скиллов)."""

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer


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

        file: UploadedFile = serializer.validated_data["file"]
        public_url: str = image_upload_handler(file_obj=file)

        return Response(
            {
                "image_url": public_url,
                "original_name": file.name,
                "file_size": file.size,
                "mime_type": file.content_type or "image/jpeg",
            },
            status=status.HTTP_201_CREATED,
        )
