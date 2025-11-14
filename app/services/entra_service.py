"""
Entra ID service for creating users and generating company email addresses.
"""

from __future__ import annotations

import re
import secrets
import string
from typing import Optional

import httpx
from app.services.auth_graph import EntraAuthClient
from app.utils.logging import get_logger

logger = get_logger("EntraService")

# Domain for company email addresses
COMPANY_DOMAIN = "Draup381.onmicrosoft.com"


class EntraServiceError(Exception):
    """Raised when Entra ID operations fail."""


class EntraService:
    """Service for interacting with Microsoft Entra ID (Azure AD) via Graph API."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """
        Initialize Entra service.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application client secret
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_client = EntraAuthClient(tenant_id, client_id, client_secret)
        self.graph_api_base = "https://graph.microsoft.com/v1.0"
        self.logger = logger

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for use in email addresses (lowercase, remove special chars).

        Args:
            name: Name string to normalize

        Returns:
            Normalized name (lowercase, alphanumeric only)
        """
        # Remove special characters, keep only alphanumeric
        normalized = re.sub(r"[^a-zA-Z0-9]", "", name)
        return normalized.lower()

    def _generate_principal_name(self, firstname: str, lastname: str) -> str:
        """
        Generate principal name in format: firstname_lastname.

        Args:
            firstname: First name
            lastname: Last name

        Returns:
            Principal name (firstname_lastname, lowercase, underscore-separated)
        """
        firstname_norm = self._normalize_name(firstname)
        lastname_norm = self._normalize_name(lastname)
        return f"{firstname_norm}_{lastname_norm}"

    def _generate_email(self, firstname: str, lastname: str) -> str:
        """
        Generate company email address in format: firstname.lastname@Draup381.onmicrosoft.com.

        Args:
            firstname: First name
            lastname: Last name

        Returns:
            Email address (firstname.lastname@Draup381.onmicrosoft.com, lowercase, dot-separated)
        """
        firstname_norm = self._normalize_name(firstname)
        lastname_norm = self._normalize_name(lastname)
        return f"{firstname_norm}.{lastname_norm}@{COMPANY_DOMAIN}"

    def _generate_display_name(self, full_name: Optional[str], firstname: str, lastname: str) -> str:
        """
        Generate display name for the user.

        Args:
            full_name: Full name with spaces (if provided)
            firstname: First name
            lastname: Last name

        Returns:
            Display name (full_name if provided, else "name@company")
        """
        if full_name and full_name.strip():
            return full_name.strip()
        # Fallback: use firstname and lastname if available
        if firstname and lastname:
            return f"{firstname} {lastname}".strip()
        # Final fallback
        return "name@company"

    def _generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a secure random password that meets Microsoft Entra ID requirements.

        Requirements:
        - At least 8 characters (we use 16 by default)
        - Contains uppercase letters, lowercase letters, numbers, and special characters
        - Uses only safe special characters that are commonly accepted by Microsoft Entra ID

        Args:
            length: Length of the password (default: 16)

        Returns:
            Secure random password string
        """
        if length < 8:
            length = 8

        # Character sets - using safe special characters commonly accepted by Entra ID
        # Avoiding: backslash, forward slash, quotes, brackets, and other potentially problematic chars
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        # Safe special characters for Microsoft Entra ID (most commonly accepted)
        # Removed brackets [] as they can sometimes cause issues in some configurations
        special_chars = "!@#$%^&*()_+-={}|;:,.<>?"

        # Ensure at least one character from each required set
        password_chars = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits),
            secrets.choice(special_chars),
        ]

        # Fill the rest with random characters from all sets
        all_chars = uppercase + lowercase + digits + special_chars
        for _ in range(length - 4):
            password_chars.append(secrets.choice(all_chars))

        # Shuffle to avoid predictable pattern (uppercase, lowercase, digit, special, then rest)
        secrets.SystemRandom().shuffle(password_chars)

        return "".join(password_chars)

    def generate_company_email(
        self,
        firstname: str,
        lastname: str,
        full_name: Optional[str] = None,
    ) -> str:
        """
        Generate a company email address and create user in Entra ID.

        Args:
            firstname: User's first name
            lastname: User's last name
            full_name: Optional full name (space-separated) for display name

        Returns:
            Generated email address (firstname.lastname@Draup381.onmicrosoft.com)

        Raises:
            EntraServiceError: If user creation fails
        """
        # Validate inputs
        if not firstname or not lastname:
            raise EntraServiceError("Both firstname and lastname are required")

        # Generate email and principal name
        email = self._generate_email(firstname, lastname)
        principal_name = self._generate_principal_name(firstname, lastname)
        display_name = self._generate_display_name(full_name, firstname, lastname)

        self.logger.info(
            "generating_company_email",
            firstname=firstname,
            lastname=lastname,
            email=email,
            principal_name=principal_name,
        )

        # Get access token
        try:
            access_token = self.auth_client.get_graph_token()
            self.logger.info("access_token_acquired", token_length=len(access_token) if access_token else 0)
        except Exception as e:
            self.logger.error("graph_token_failed", error=str(e))
            raise EntraServiceError(f"Failed to get access token: {str(e)}") from e

        # Generate secure temporary password
        temp_password = self._generate_secure_password()

        # Create user in Entra ID via Microsoft Graph API
        user_payload = {
            "accountEnabled": True,
            "displayName": display_name,
            "mailNickname": principal_name,
            "userPrincipalName": email,
            "passwordProfile": {
                "password": temp_password,
                "forceChangePasswordNextSignIn": True,
            },
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        create_user_url = f"{self.graph_api_base}/users"

        try:
            self.logger.info(
                "creating_user_in_entra",
                url=create_user_url,
                user_payload_keys=list(user_payload.keys()),
                display_name=display_name,
                email=email,
            )
            with httpx.Client(timeout=30.0) as client:
                response = client.post(create_user_url, json=user_payload, headers=headers)
                self.logger.info(
                    "entra_api_response",
                    status_code=response.status_code,
                    response_preview=response.text[:500] if response.status_code != 201 else None,
                )
                response.raise_for_status()
                created_user = response.json()

                self.logger.info(
                    "user_created_in_entra",
                    email=email,
                    user_id=created_user.get("id"),
                    display_name=display_name,
                )

                return email

        except httpx.HTTPStatusError as e:
            error_detail = ""
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("error", {}).get("message", str(e))
                except Exception:
                    error_detail = e.response.text or str(e)

            self.logger.error(
                "entra_user_creation_failed",
                email=email,
                status_code=e.response.status_code if e.response else None,
                error=error_detail,
            )
            raise EntraServiceError(
                f"Failed to create user in Entra ID: {error_detail} (Status: {e.response.status_code if e.response else 'Unknown'})"
            ) from e
        except httpx.RequestError as e:
            self.logger.error("entra_request_failed", email=email, error=str(e))
            raise EntraServiceError(f"Request to Entra ID failed: {str(e)}") from e
        except Exception as e:
            self.logger.error(
                "unexpected_error_creating_user",
                email=email,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EntraServiceError(f"Unexpected error creating user in Entra ID: {str(e)}") from e

