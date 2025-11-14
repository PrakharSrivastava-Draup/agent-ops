"""
User management service for handling user onboarding and POC configurations.
"""

from typing import Any, Dict, List, Optional

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

