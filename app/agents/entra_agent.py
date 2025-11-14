"""
Entra ID agent for generating company email addresses and creating users in Entra ID.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.config import Settings, get_settings
from app.services.entra_service import EntraService, EntraServiceError
from app.utils.logging import get_logger

logger = get_logger("EntraAgent")


class EntraAgent(BaseAgent):
    """Agent for generating company email addresses and creating users in Microsoft Entra ID."""

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """
        Initialize Entra agent.

        Args:
            tenant_id: Optional Azure AD tenant ID (uses settings if not provided)
            client_id: Optional Azure AD application (client) ID (uses settings if not provided)
            client_secret: Optional Azure AD application client secret (uses settings if not provided)
            settings: Optional Settings instance (uses get_settings() if not provided)
        """
        super().__init__("EntraAgent")
        if settings is None:
            settings = get_settings()
        self.settings = settings
        self.tenant_id = tenant_id or settings.entra_tenant_id
        self.client_id = client_id or settings.entra_client_id
        self.client_secret = client_secret or settings.entra_client_secret
        self._log_info("Initialized Entra agent")

    async def generate_company_email(
        self,
        firstname: str,
        lastname: str,
        full_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Generate a company email address and create user in Entra ID.

        Args:
            firstname: User's first name
            lastname: User's last name
            full_name: Optional full name (space-separated) for display name
            **kwargs: Additional parameters (ignored)

        Returns:
            AgentResponse with generated email address

        Raises:
            AgentError: If validation fails or Entra service fails
        """
        # Validate inputs
        if not firstname or not lastname:
            raise AgentError("Both firstname and lastname are required")

        # Validate Entra credentials are configured
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise AgentError(
                "Entra ID credentials not configured. Please set TENANT_ID, CLIENT_ID, and CLIENT_SECRET environment variables."
            )

        self._log_info(
            "generating_company_email",
            firstname=firstname,
            lastname=lastname,
            has_full_name=full_name is not None,
        )

        # Create Entra service and generate email (run in thread pool since it's sync)
        try:
            entra_service = EntraService(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            generated_email = await asyncio.to_thread(
                entra_service.generate_company_email,
                firstname=firstname,
                lastname=lastname,
                full_name=full_name,
            )

            response_data = {
                "success": True,
                "email": generated_email,
                "firstname": firstname,
                "lastname": lastname,
                "display_name": full_name or f"{firstname} {lastname}",
            }

            self._log_info(
                "company_email_generated",
                email=generated_email,
                firstname=firstname,
                lastname=lastname,
            )

            return AgentResponse(data=response_data)

        except EntraServiceError as e:
            self._log_error(
                "entra_email_generation_failed",
                firstname=firstname,
                lastname=lastname,
                error=str(e),
            )
            raise AgentError(f"Failed to generate company email: {str(e)}") from e
        except Exception as e:
            self._log_error(
                "unexpected_error",
                firstname=firstname,
                lastname=lastname,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentError(f"Unexpected error generating company email: {str(e)}") from e

