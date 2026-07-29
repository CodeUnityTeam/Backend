from typing import Any

from config.celery import celery_app
from users.utils import email_service


@celery_app.task(name='core.tasks.send_async_template_email')
def send_async_template_email(
    to_email: str,
    subject: str,
    template_base_name: str,
    context: dict[str, Any],
) -> None:
    """Асинхронная задача Celery для отправки шаблонных писем."""
    email_service.send_template_email(
        to_email=to_email,
        subject=subject,
        template_base_name=template_base_name,
        context=context,
    )
