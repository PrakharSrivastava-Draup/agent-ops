"""
Email service for sending notifications.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, List, Optional
from app.utils.logging import get_logger

logger = get_logger("EmailService")


class EmailServiceError(Exception):
    """Exception raised for email service errors."""


class EmailService:
    """Service for sending email notifications."""

    def __init__(
        self,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "toofanpersonal23@gmail.com",
        sender_password: Optional[str] = None,
    ):
        """
        Initialize email service.

        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            sender_email: Email address to send from
            sender_password: Password for sender email (if None, will try to get from environment)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self._log_info("email_service_initialized", smtp_server=smtp_server, sender_email=sender_email)

    def _log_info(self, message: str, **kwargs: Any) -> None:
        logger.info(message, **kwargs)

    def _log_error(self, message: str, **kwargs: Any) -> None:
        logger.error(message, **kwargs)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc_emails: Optional[List[str]] = None,
    ) -> None:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            cc_emails: Optional list of CC email addresses

        Raises:
            EmailServiceError: If email sending fails
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = to_email
            msg["Subject"] = subject

            if cc_emails:
                msg["Cc"] = ", ".join(cc_emails)

            # Add body to email
            msg.attach(MIMEText(body, "plain"))

            # Get sender password
            password = self.sender_password
            if not password:
                import os
                password = os.getenv("SMTP_PASSWORD")
                if not password:
                    raise EmailServiceError(
                        "SMTP password not provided. Set sender_password or SMTP_PASSWORD environment variable."
                    )

            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable TLS encryption
            server.login(self.sender_email, password)

            # Send email
            recipients = [to_email]
            if cc_emails:
                recipients.extend(cc_emails)

            text = msg.as_string()
            server.sendmail(self.sender_email, recipients, text)
            server.quit()

            self._log_info(
                "email_sent",
                to_email=to_email,
                subject=subject,
                cc_emails=cc_emails,
            )

        except smtplib.SMTPException as e:
            self._log_error(
                "email_send_failed",
                to_email=to_email,
                subject=subject,
                error=str(e),
            )
            raise EmailServiceError(f"Failed to send email: {str(e)}") from e
        except Exception as e:
            self._log_error(
                "email_send_unexpected_error",
                to_email=to_email,
                subject=subject,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailServiceError(f"Unexpected error sending email: {str(e)}") from e

