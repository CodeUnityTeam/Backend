from typing import Any, Dict

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class EmailService:
    """Сервис для подготовки и отправки email-уведомлений."""

    def _prepare_message(
        self,
        to_email: str,
        subject: str,
        template_base_name: str,
        context: Dict[str, Any],
    ) -> EmailMultiAlternatives:
        """Рендерить HTML и TXT шаблоны и собирает EmailMultiAlternatives."""
        current_site = Site.objects.get_current()
        full_context = {
            'current_site': current_site,
            **context,
        }

        text_content = render_to_string(
            f'{template_base_name}.txt', full_context,
        )
        html_content = render_to_string(
            f'{template_base_name}.html', full_context,
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        message.attach_alternative(html_content, 'text/html')
        return message

    def _send_raw_mail(self, message: EmailMultiAlternatives) -> None:
        """Отправить сообщение через настроенный Email Backend."""
        message.send()

    def send_template_email(
        self,
        to_email: str,
        subject: str,
        template_base_name: str,
        context: Dict[str, Any],
    ) -> None:
        """Публичный интерфейс для отправки шаблонных писем (HTML + TXT)."""
        message = self._prepare_message(
            to_email=to_email,
            subject=subject,
            template_base_name=template_base_name,
            context=context,
        )
        self._send_raw_mail(message)


email_service = EmailService()
