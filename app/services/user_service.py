"""
User management service for handling user onboarding and POC configurations.
"""

from typing import Any, Dict, List, Optional

from app.config import Settings, get_settings
from app.services.entra_service import EntraService, EntraServiceError
from app.services.user_db import UserDB, UserDBError
from app.utils.logging import get_logger

logger = get_logger("user_service")


class UserServiceError(Exception):
    """Raised when user service operations fail."""


class UserService:
    """Service for managing users and POC configurations."""

    def __init__(self, db: UserDB) -> None:
        """
        Initialize user service.

        Args:
            db: UserDB instance for database operations
        """
        self.db = db

    def onboard_user(
        self,
        name: str,
        emailid: str,
        contact_no: str,
        location: str,
        date_of_joining: str,
        level: str,
        team: str,
        manager: str,
    ) -> Dict[str, Any]:
        """
        Onboard a new user.

        Fetches POC config entries for the team, builds access_items_status,
        and inserts the user with status='new'.

        Returns:
            Dictionary with user data including the generated ID.
        """
        try:
            # Fetch POC config entries for the team
            poc_configs = self.db.get_poc_config_by_team(team)

            # Extract unique access items
            access_items = set()
            for config in poc_configs:
                access_items.add(config["access_item"])

            # Build access_items_status with default values
            access_items_status = [
                {"item": item, "status": "pending", "timestamp": None}
                for item in sorted(access_items)
            ]

            # Insert user
            user_id = self.db.insert_user(
                name=name,
                emailid=emailid,
                contact_no=contact_no,
                location=location,
                date_of_joining=date_of_joining,
                level=level,
                team=team,
                manager=manager,
                status="new",
                access_items_status=access_items_status,
            )

            logger.info("user_onboarded", user_id=user_id, emailid=emailid, team=team)

            # Return user data
            return {
                "id": user_id,
                "name": name,
                "emailid": emailid,
                "contact_no": contact_no,
                "location": location,
                "date_of_joining": date_of_joining,
                "level": level,
                "team": team,
                "manager": manager,
                "status": "new",
                "access_items_status": access_items_status,
            }
        except UserDBError as exc:
            logger.error("onboard_user_failed", error=str(exc))
            raise UserServiceError(f"Failed to onboard user: {exc}") from exc

    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Get all users with their status.

        Returns:
            List of user dictionaries with all fields including access_items_status.
        """
        try:
            users = self.db.get_all_users()
            logger.info("users_retrieved", count=len(users))
            return users
        except UserDBError as exc:
            logger.error("get_all_users_failed", error=str(exc))
            raise UserServiceError(f"Failed to retrieve users: {exc}") from exc

    def get_all_poc_configs(self) -> List[Dict[str, Any]]:
        """
        Get all POC config entries.

        Returns:
            List of POC config dictionaries with all fields.
        """
        try:
            configs = self.db.get_all_poc_configs()
            logger.info("poc_configs_retrieved", count=len(configs))
            return configs
        except UserDBError as exc:
            logger.error("get_all_poc_configs_failed", error=str(exc))
            raise UserServiceError(f"Failed to retrieve POC configs: {exc}") from exc

    def add_poc_config(self, config_entries: List[Dict[str, Any]]) -> List[int]:
        """
        Add POC configuration entries.

        For each entry, creates one row per access_item (denormalized).

        Args:
            config_entries: List of dictionaries with role, team, access_items, poc_id

        Returns:
            List of inserted config IDs.
        """
        try:
            inserted_ids = []
            for entry in config_entries:
                role = entry["role"]
                team = entry["team"]
                access_items = entry["access_items"]
                poc_id = entry["poc_id"]

                # Insert one row per access_item
                for access_item in access_items:
                    config_id = self.db.insert_poc_config(
                        role=role,
                        team=team,
                        access_item=access_item,
                        poc_id=poc_id,
                    )
                    inserted_ids.append(config_id)

            logger.info("poc_config_added", entries_count=len(config_entries), rows_inserted=len(inserted_ids))
            return inserted_ids
        except UserDBError as exc:
            logger.error("add_poc_config_failed", error=str(exc))
            raise UserServiceError(f"Failed to add POC config: {exc}") from exc

    def update_user_status(
        self,
        emailid: str,
        status: Optional[str],
        access_items_status: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Update user status and access items.

        Args:
            emailid: User email to identify the user
            status: Optional overall user status to update
            access_items_status: List of dicts with 'item' and 'status' keys

        Returns:
            Updated user data dictionary

        Raises:
            UserServiceError: If validation fails or database operation fails
        """
        # Validate access item statuses
        valid_statuses = {"pending", "in progress", "completed"}
        for item_update in access_items_status:
            item_status = item_update.get("status")
            if item_status not in valid_statuses:
                raise UserServiceError(
                    f"Invalid access item status '{item_status}'. Must be one of: {', '.join(valid_statuses)}"
                )

        try:
            user_data = self.db.update_user_status_and_access_items(
                emailid=emailid,
                status=status,
                access_items_updates=access_items_status,
            )
            logger.info("user_status_updated", emailid=emailid, status_updated=status is not None)
            return user_data
        except UserDBError as exc:
            logger.error("update_user_status_failed", emailid=emailid, error=str(exc))
            raise UserServiceError(f"Failed to update user status: {exc}") from exc

    def generate_and_update_email(
        self,
        user_id: int,
        firstname: str,
        lastname: str,
        full_name: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> str:
        """
        Generate a company email address using Entra service and update user record in DB.

        Args:
            user_id: ID of the user to update
            firstname: User's first name
            lastname: User's last name
            full_name: Optional full name (space-separated) for display name
            settings: Optional Settings instance. If not provided, will fetch from get_settings().

        Returns:
            Generated email address

        Raises:
            UserServiceError: If Entra service fails or database update fails
        """
        if settings is None:
            settings = get_settings()

        # Validate Entra credentials are configured
        if not settings.entra_tenant_id or not settings.entra_client_id or not settings.entra_client_secret:
            raise UserServiceError(
                "Entra ID credentials not configured. Please set TENANT_ID, CLIENT_ID, and CLIENT_SECRET environment variables."
            )

        try:
            # Get current user to find their current emailid
            users = self.db.get_all_users()
            user = None
            for u in users:
                if u.get("id") == user_id:
                    user = u
                    break

            if not user:
                raise UserServiceError(f"User with ID {user_id} not found")

            # Create Entra service and generate email
            entra_service = EntraService(
                tenant_id=settings.entra_tenant_id,
                client_id=settings.entra_client_id,
                client_secret=settings.entra_client_secret,
            )

            generated_email = entra_service.generate_company_email(
                firstname=firstname,
                lastname=lastname,
                full_name=full_name,
            )

            # Update user email in database (by user ID to handle empty emails)
            self.db.update_user_emailid(user_id=user_id, new_emailid=generated_email)

            logger.info(
                "email_generated_and_updated",
                user_id=user_id,
                new_emailid=generated_email,
            )

            return generated_email

        except EntraServiceError as exc:
            logger.error("entra_email_generation_failed", user_id=user_id, error=str(exc))
            raise UserServiceError(f"Failed to generate company email: {exc}") from exc
        except UserDBError as exc:
            logger.error("email_update_failed", user_id=user_id, error=str(exc))
            raise UserServiceError(f"Failed to update user email in database: {exc}") from exc

    def delete_user(self, user_id: int) -> None:
        """
        Delete a user by ID.

        Args:
            user_id: ID of the user to delete

        Raises:
            UserServiceError: If database operation fails
        """
        try:
            self.db.delete_user_by_id(user_id)
            logger.info("user_deleted", user_id=user_id)
        except UserDBError as exc:
            logger.error("delete_user_failed", user_id=user_id, error=str(exc))
            raise UserServiceError(f"Failed to delete user: {exc}") from exc

    def delete_user_email_by_name(self, name: str) -> Dict[str, Any]:
        """
        Delete email address for a user by name.
        Sets emailid to empty string.

        Args:
            name: User name to identify the user

        Returns:
            Updated user data dictionary

        Raises:
            UserServiceError: If user not found or database operation fails
        """
        try:
            user_data = self.db.delete_email_by_name(name)
            logger.info("user_email_deleted_by_name", name=name, user_id=user_data.get("id"))
            return user_data
        except UserDBError as exc:
            logger.error("delete_user_email_by_name_failed", name=name, error=str(exc))
            raise UserServiceError(f"Failed to delete email for user '{name}': {exc}") from exc

