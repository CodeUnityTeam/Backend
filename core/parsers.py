from typing import Any

from django.core.files.uploadhandler import (
    StopUpload,
    TemporaryFileUploadHandler,
)
from rest_framework.parsers import MultiPartParser


class QuotaUploadHandler(TemporaryFileUploadHandler):
    """Потоковый ограничитель размера файлов."""

    def __init__(self, max_bytes: int, *args: Any, **kwargs: Any) -> None:
        """Установить максимальный размер загружаемого потока."""
        super().__init__(*args, **kwargs)
        self.max_bytes: int = max_bytes

    def receive_data_chunk(self, raw_data: bytes, start: int) -> bytes:
        """Проверяет размер чанка на лету."""
        if start + len(raw_data) > self.max_bytes:
            raise StopUpload(connection_reset=True)
        return raw_data


class StrictXParser(MultiPartParser):
    """Парсер с динамическим лимитом размера из View."""

    default_file_size: int = 10 * 1024 * 1024

    def parse(self, stream: Any, media_type: Any, parser_context: Any) -> Any:
        """Парсит запрос, динамически ограничивая размер потока из View."""
        req = parser_context["request"]
        view = parser_context.get("view")

        # Или ограничение из View, или дефолтное из класса
        max_bytes: int = getattr(
            view, "allow_upload_size", self.default_file_size,
        )

        req.upload_handlers = [
            QuotaUploadHandler(max_bytes=max_bytes, request=req),
        ]
        return super().parse(stream, media_type, parser_context)
