from __future__ import annotations

from typing import Optional

from msal import ConfidentialClientApplication

from app.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger("EntraAuthClient")


class EntraAuthClient:
    """Client for authenticating with Microsoft Entra ID (Azure AD) using MSAL."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """
        Initialize Entra authentication client.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application client secret
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.app = ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        logger.info("entra_auth_client_initialized", tenant_id=tenant_id[:8] + "***")

    def get_graph_token(self) -> str:
        """Get an app-only access token for Microsoft Graph."""
        result = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            error_msg = result.get("error_description") or str(result)
            logger.error("graph_token_acquisition_failed", error=error_msg)
            raise RuntimeError(f"Could not get access token: {error_msg}")
        logger.info("graph_token_acquired")
        return result["access_token"]


def get_graph_token(settings: Optional[Settings] = None) -> str:
    """
    Get an app-only access token for Microsoft Graph.

    Args:
        settings: Optional Settings instance. If not provided, will fetch from get_settings().

    Returns:
        Access token string for Microsoft Graph API

    Raises:
        RuntimeError: If credentials are not configured or token acquisition fails
    """
    if settings is None:
        settings = get_settings()

    if not settings.entra_tenant_id or not settings.entra_client_id or not settings.entra_client_secret:
        raise RuntimeError(
            "Entra ID credentials not configured. Please set TENANT_ID, CLIENT_ID, and CLIENT_SECRET environment variables."
        )

    client = EntraAuthClient(
        tenant_id=settings.entra_tenant_id,
        client_id=settings.entra_client_id,
        client_secret=settings.entra_client_secret,
    )
    return client.get_graph_token()