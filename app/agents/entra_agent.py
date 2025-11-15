"""
Entra ID agent for generating company email addresses and creating users in Entra ID.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.config import Settings, get_settings
from app.services.entra_service import EntraService, EntraServiceError
from app.services.user_db import UserDB, UserDBError
from app.services.user_service import UserService, UserServiceError
from app.services.email_service import EmailService, EmailServiceError
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

    async def generate_and_save_email(
        self,
        user_id: Optional[int] = None,
        name: Optional[str] = None,
        firstname: Optional[str] = None,
        lastname: Optional[str] = None,
        full_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Generate a company email address using Entra service and save it to the database.

        Requires either:
        - user_id: ID of the user to update (preferred)
        - name: Name of the user to update (if user_id not provided)

        If user_id is provided, will use existing user data. If name is provided, will find user by name.
        If firstname/lastname are provided, they will be used for email generation.
        Otherwise, will extract from user's name in database.

        Args:
            user_id: Optional user ID to identify the user
            name: Optional user name to identify the user (if user_id not provided)
            firstname: Optional first name for email generation (extracted from user name if not provided)
            lastname: Optional last name for email generation (extracted from user name if not provided)
            full_name: Optional full name (space-separated) for display name
            **kwargs: Additional parameters (ignored)

        Returns:
            AgentResponse with generated email and updated user data

        Raises:
            AgentError: If validation fails, user not found, or Entra service fails
        """
        # Validate that either user_id or name is provided
        if not user_id and not name:
            raise AgentError("Either user_id or name must be provided")

        # Validate Entra credentials are configured
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise AgentError(
                "Entra ID credentials not configured. Please set TENANT_ID, CLIENT_ID, and CLIENT_SECRET environment variables."
            )

        # Create UserDB instance (same pattern as UserService)
        settings = get_settings()
        user_db = UserDB(db_path=settings.user_db_path)

        # Find user in database
        user = None
        if user_id:
            # Get user by ID
            try:
                all_users = user_db.get_all_users()
                for u in all_users:
                    if u.get("id") == user_id:
                        user = u
                        break
                if not user:
                    raise AgentError(f"User with ID {user_id} not found")
            except UserDBError as e:
                raise AgentError(f"Failed to fetch user by ID: {str(e)}") from e
        elif name:
            # Get user by name (case-insensitive)
            try:
                users = user_db.get_users_by_name(name)
                if not users:
                    raise AgentError(f"User with name '{name}' not found")
                if len(users) > 1:
                    # Multiple users with same name - use the first one
                    self._log_info(
                        "multiple_users_with_name",
                        name=name,
                        count=len(users),
                        using_id=users[0].get("id"),
                    )
                user = users[0]
                user_id = user["id"]
            except UserDBError as e:
                raise AgentError(f"Failed to fetch user by name: {str(e)}") from e

        # Extract firstname and lastname
        if not firstname or not lastname:
            # Extract from user name
            user_name = user.get("name", "")
            name_parts = user_name.strip().split()
            if len(name_parts) < 2:
                # If only one name part, use it as both first and last name
                extracted_firstname = name_parts[0] if name_parts else "User"
                extracted_lastname = name_parts[0] if name_parts else "User"
            else:
                # First part is firstname, rest is lastname
                extracted_firstname = name_parts[0]
                extracted_lastname = " ".join(name_parts[1:])
            
            # Use provided values or extracted values
            final_firstname = firstname or extracted_firstname
            final_lastname = lastname or extracted_lastname
        else:
            final_firstname = firstname
            final_lastname = lastname

        # Use full_name from user if not provided
        if not full_name:
            full_name = user.get("name")

        self._log_info(
            "generating_and_saving_email",
            user_id=user_id,
            name=user.get("name"),
            firstname=final_firstname,
            lastname=final_lastname,
        )

        # Generate email using Entra service
        try:
            # Add entry to ai_live_reasoning
            try:
                user_db.append_ai_live_reasoning(
                    message=f"Generating company email address using Entra ID for {final_firstname} {final_lastname}",
                    user_id=user_id,
                )
            except Exception as e:
                # Log but don't fail if reasoning update fails
                logger.warning("failed_to_add_reasoning_entry", error=str(e))
            
            entra_service = EntraService(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            generated_email = await asyncio.to_thread(
                entra_service.generate_company_email,
                firstname=final_firstname,
                lastname=final_lastname,
                full_name=full_name,
            )

            # Add entry to ai_live_reasoning after email generation
            try:
                user_db.append_ai_live_reasoning(
                    message=f"Successfully generated email {generated_email} and created user in Microsoft Entra ID",
                    user_id=user_id,
                )
            except Exception as e:
                # Log but don't fail if reasoning update fails
                logger.warning("failed_to_add_reasoning_entry", error=str(e))

            # Save email to database
            try:
                # Ensure user_id is an integer
                if not isinstance(user_id, int):
                    raise AgentError(f"Invalid user_id type: {type(user_id)}, expected int")
                
                self._log_info(
                    "updating_user_email",
                    user_id=user_id,
                    current_email=user.get("emailid"),
                    new_email=generated_email,
                )
                
                user_db.update_user_emailid(user_id=user_id, new_emailid=generated_email)
                
                # Add entry to ai_live_reasoning after saving
                try:
                    user_db.append_ai_live_reasoning(
                        message=f"Saved email {generated_email} to user database",
                        user_id=user_id,
                    )
                except Exception as e:
                    # Log but don't fail if reasoning update fails
                    logger.warning("failed_to_add_reasoning_entry", error=str(e))
                
                self._log_info(
                    "email_generated_and_saved",
                    user_id=user_id,
                    generated_email=generated_email,
                )
                
                # Verify the update succeeded by fetching the user again
                all_users_after_update = user_db.get_all_users()
                updated_user_verify = None
                for u in all_users_after_update:
                    if u.get("id") == user_id:
                        updated_user_verify = u
                        break
                
                if not updated_user_verify:
                    raise AgentError(f"User with ID {user_id} not found after update")
                
                if updated_user_verify.get("emailid") != generated_email:
                    self._log_error(
                        "email_update_verification_failed",
                        user_id=user_id,
                        expected_email=generated_email,
                        actual_email=updated_user_verify.get("emailid"),
                    )
                    raise AgentError(
                        f"Email update verification failed. Expected: {generated_email}, "
                        f"Got: {updated_user_verify.get('emailid')}"
                    )
                
                self._log_info(
                    "email_update_verified",
                    user_id=user_id,
                    verified_email=updated_user_verify.get("emailid"),
                )
                
                # Send notification email to suchanya.p@draup.com
                try:
                    email_service = EmailService()
                    user_name = updated_user_verify.get("name", "User")
                    email_subject = "This is a test mail for hackethon"
                    email_body = f"""Dear Team,

This is to inform you that the SSO email account has been successfully created for the following user:

User Name: {user_name}
Email Address: {generated_email}

The user account has been provisioned in Microsoft Entra ID and is ready for use.

Best regards,
Agent Ops System"""
                    
                    await asyncio.to_thread(
                        email_service.send_email,
                        to_email="prakhar.srivastava@draup.com",
                        subject=email_subject,
                        body=email_body,
                    )
                    self._log_info(
                        "entra_email_notification_sent",
                        user_id=user_id,
                        user_email=generated_email,
                        recipient="prakhar.srivastava@draup.com",
                    )
                except Exception as e:
                    # Log error but don't fail the response - email generation was successful
                    self._log_error(
                        "entra_email_notification_failed",
                        user_id=user_id,
                        user_email=generated_email,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                
                # Update Email/SSO status to 'completed' in access_items_status
                warnings_list = []
                try:
                    await self._update_email_sso_status(user_id=user_id, user_email=generated_email)
                except Exception as e:
                    # Log error but don't fail the response - email generation was successful
                    self._log_error(
                        "email_sso_status_update_failed",
                        user_id=user_id,
                        user_email=generated_email,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Add warning to response
                    warnings_list.append(
                        f"Email generation succeeded but failed to update Email/SSO status: {str(e)}"
                    )
                
            except UserDBError as e:
                raise AgentError(f"Failed to save email to database: {str(e)}") from e

            # Get updated user data
            try:
                updated_users = user_db.get_all_users()
                updated_user = None
                for u in updated_users:
                    if u.get("id") == user_id:
                        updated_user = u
                        break
                
                response_data = {
                    "success": True,
                    "email": generated_email,
                    "firstname": final_firstname,
                    "lastname": final_lastname,
                    "display_name": full_name or f"{final_firstname} {final_lastname}",
                    "user_id": user_id,
                    "user_name": updated_user.get("name") if updated_user else user.get("name"),
                }

                self._log_info(
                    "generate_and_save_email_completed",
                    user_id=user_id,
                    email=generated_email,
                )

                # Include warnings if any
                response_warnings = warnings_list if warnings_list else None
                return AgentResponse(data=response_data, warnings=response_warnings)

            except UserDBError as e:
                # Email was saved but failed to fetch updated user - still return success
                self._log_error("failed_to_fetch_updated_user", user_id=user_id, error=str(e))
                response_data = {
                    "success": True,
                    "email": generated_email,
                    "firstname": final_firstname,
                    "lastname": final_lastname,
                    "display_name": full_name or f"{final_firstname} {final_lastname}",
                    "user_id": user_id,
                    "warning": f"Email generated and saved, but failed to fetch updated user: {str(e)}",
                }
                return AgentResponse(data=response_data, warnings=[response_data["warning"]])

        except EntraServiceError as e:
            self._log_error(
                "entra_email_generation_failed",
                user_id=user_id,
                error=str(e),
            )
            raise AgentError(f"Failed to generate company email: {str(e)}") from e
        except Exception as e:
            self._log_error(
                "unexpected_error",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentError(f"Unexpected error generating and saving email: {str(e)}") from e

    async def _update_email_sso_status(
        self,
        user_id: int,
        user_email: str,
    ) -> None:
        """
        Update access_items_status for Email/SSO to 'completed' after successful email generation.
        
        Args:
            user_id: User ID to identify the user
            user_email: User email address (for logging and identification)
        """
        try:
            # Get settings and create UserService
            settings = get_settings()
            user_db = UserDB(db_path=settings.user_db_path)
            user_service = UserService(db=user_db)
            
            # Find user by ID
            user = None
            all_users = user_db.get_all_users()
            for u in all_users:
                if u.get("id") == user_id:
                    user = u
                    break
            
            if not user:
                self._log_warning(
                    "user_not_found_for_email_sso_update",
                    user_id=user_id,
                    user_email=user_email,
                )
                return
            
            # Get current access_items_status
            access_items_status = user.get("access_items_status", [])
            
            # Possible names for Email/SSO item (case-insensitive matching)
            email_sso_names = ["email", "sso", "email/sso", "email & sso", "email and sso", "entra", "microsoft entra", "entra id"]
            
            # Prepare updates for Email/SSO items
            access_items_updates = []
            for item in access_items_status:
                item_name = item.get("item", "").strip()
                item_status = item.get("status", "").strip()
                
                # Normalize item name for comparison
                item_name_normalized = item_name.lower().strip()
                
                # Check if this item matches any Email/SSO variations
                if item_name_normalized in email_sso_names:
                    # Update to 'completed' status
                    access_items_updates.append({
                        "item": item_name,  # Use original item name from DB
                        "status": "completed",
                    })
                    self._log_info(
                        "email_sso_item_marked_for_completion",
                        user_id=user_id,
                        user_email=user_email,
                        item=item_name,
                    )
            
            # Only update if there are items to update
            if not access_items_updates:
                self._log_warning(
                    "no_matching_email_sso_items_for_update",
                    user_id=user_id,
                    user_email=user_email,
                    access_items=[item.get("item") for item in access_items_status],
                )
                return
            
            # Update user status
            user_service.update_user_status(
                emailid=user_email,
                status=None,  # Don't update overall status
                access_items_status=access_items_updates,
            )
            
            self._log_info(
                "email_sso_status_updated",
                user_id=user_id,
                user_email=user_email,
                updated_items_count=len(access_items_updates),
                updated_items=[item["item"] for item in access_items_updates],
            )
            
        except UserServiceError as e:
            self._log_error(
                "user_service_error_updating_email_sso",
                user_id=user_id,
                user_email=user_email,
                error=str(e),
            )
            raise
        except UserDBError as e:
            self._log_error(
                "user_db_error_updating_email_sso",
                user_id=user_id,
                user_email=user_email,
                error=str(e),
            )
            raise
        except Exception as e:
            self._log_error(
                "unexpected_error_updating_email_sso",
                user_id=user_id,
                user_email=user_email,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

