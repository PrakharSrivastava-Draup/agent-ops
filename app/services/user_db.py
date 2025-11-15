"""
SQLite database setup and connection management for user management service.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("user_db")


class UserDBError(Exception):
    """Raised when database operations fail."""


class UserDB:
    """SQLite database manager for user management."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default from settings.
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.user_db_path

        # Ensure directory exists
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_file)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create user table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE,
                        emailid TEXT,
                        contact_no TEXT,
                        location TEXT,
                        date_of_joining TEXT,
                        level TEXT,
                        team TEXT,
                        manager TEXT,
                        status TEXT,
                        access_items_status TEXT,
                        ai_live_reasoning TEXT
                    )
                """)
                
                # Add ai_live_reasoning column if it doesn't exist (for existing databases)
                try:
                    cursor.execute("""
                        ALTER TABLE user ADD COLUMN ai_live_reasoning TEXT
                    """)
                    logger.info("ai_live_reasoning_column_added")
                except sqlite3.OperationalError:
                    # Column already exists, ignore
                    pass
                
                # Add unique constraint on name if table already exists and constraint doesn't exist
                # This handles the case where the table was created before the unique constraint
                try:
                    cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_name_unique ON user(name)
                    """)
                except sqlite3.OperationalError:
                    # Index might already exist, ignore
                    pass

                # Create poc_config table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS poc_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT,
                        team TEXT,
                        access_item TEXT,
                        poc_id TEXT
                    )
                """)

                conn.commit()
                logger.info("database_initialized", db_path=self.db_path)
        except sqlite3.Error as exc:
            logger.error("database_init_failed", error=str(exc))
            raise UserDBError(f"Failed to initialize database: {exc}") from exc

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def insert_user(
        self,
        name: str,
        emailid: str,
        contact_no: str,
        location: str,
        date_of_joining: str,
        level: str,
        team: str,
        manager: str,
        status: str,
        access_items_status: List[Dict[str, Any]],
    ) -> int:
        """
        Insert a new user into the database.

        Returns:
            The ID of the inserted user.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                access_items_json = json.dumps(access_items_status)
                # Default ai_live_reasoning to empty array
                ai_live_reasoning_json = json.dumps([])
                cursor.execute("""
                    INSERT INTO user (
                        name, emailid, contact_no, location, date_of_joining,
                        level, team, manager, status, access_items_status, ai_live_reasoning
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, emailid, contact_no, location, date_of_joining,
                    level, team, manager, status, access_items_json, ai_live_reasoning_json
                ))
                user_id = cursor.lastrowid
                conn.commit()
                logger.info("user_inserted", user_id=user_id, emailid=emailid)
                return user_id
        except sqlite3.Error as exc:
            logger.error("user_insert_failed", error=str(exc))
            raise UserDBError(f"Failed to insert user: {exc}") from exc

    def get_user_by_emailid(self, emailid: str) -> Optional[Dict[str, Any]]:
        """Get a user by emailid from the database."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user WHERE emailid = ?", (emailid,))
                row = cursor.fetchone()
                if row is None:
                    return None
                user_dict = dict(row)
                # Parse JSON access_items_status
                if user_dict.get("access_items_status"):
                    user_dict["access_items_status"] = json.loads(user_dict["access_items_status"])
                else:
                    user_dict["access_items_status"] = []
                # Parse JSON ai_live_reasoning
                if user_dict.get("ai_live_reasoning"):
                    user_dict["ai_live_reasoning"] = json.loads(user_dict["ai_live_reasoning"])
                else:
                    user_dict["ai_live_reasoning"] = []
                logger.info("user_fetched_by_email", emailid=emailid)
                return user_dict
        except sqlite3.Error as exc:
            logger.error("user_fetch_by_email_failed", emailid=emailid, error=str(exc))
            raise UserDBError(f"Failed to fetch user by email: {exc}") from exc

    def get_users_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Get all users with a given name (case-insensitive).

        Args:
            name: User name to search for

        Returns:
            List of user dictionaries matching the name
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Use LOWER for case-insensitive comparison
                cursor.execute("SELECT * FROM user WHERE LOWER(name) = LOWER(?)", (name,))
                rows = cursor.fetchall()
                users = []
                for row in rows:
                    user_dict = dict(row)
                    # Parse JSON access_items_status
                    if user_dict.get("access_items_status"):
                        user_dict["access_items_status"] = json.loads(user_dict["access_items_status"])
                    else:
                        user_dict["access_items_status"] = []
                    # Parse JSON ai_live_reasoning
                    if user_dict.get("ai_live_reasoning"):
                        user_dict["ai_live_reasoning"] = json.loads(user_dict["ai_live_reasoning"])
                    else:
                        user_dict["ai_live_reasoning"] = []
                    users.append(user_dict)
                logger.info("users_fetched_by_name", name=name, count=len(users))
                return users
        except sqlite3.Error as exc:
            logger.error("users_fetch_by_name_failed", name=name, error=str(exc))
            raise UserDBError(f"Failed to fetch users by name: {exc}") from exc

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user ORDER BY id")
                rows = cursor.fetchall()
                users = []
                for row in rows:
                    user_dict = dict(row)
                    # Parse JSON access_items_status
                    if user_dict.get("access_items_status"):
                        user_dict["access_items_status"] = json.loads(user_dict["access_items_status"])
                    else:
                        user_dict["access_items_status"] = []
                    # Parse JSON ai_live_reasoning
                    if user_dict.get("ai_live_reasoning"):
                        user_dict["ai_live_reasoning"] = json.loads(user_dict["ai_live_reasoning"])
                    else:
                        user_dict["ai_live_reasoning"] = []
                    users.append(user_dict)
                logger.info("users_fetched", count=len(users))
                return users
        except sqlite3.Error as exc:
            logger.error("users_fetch_failed", error=str(exc))
            raise UserDBError(f"Failed to fetch users: {exc}") from exc

    def get_all_poc_configs(self) -> List[Dict[str, Any]]:
        """
        Get all POC config entries from the database.

        Returns:
            List of dictionaries with id, role, team, access_item, poc_id
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM poc_config ORDER BY id")
                rows = cursor.fetchall()
                configs = [dict(row) for row in rows]
                logger.info("poc_configs_fetched", count=len(configs))
                return configs
        except sqlite3.Error as exc:
            logger.error("poc_configs_fetch_failed", error=str(exc))
            raise UserDBError(f"Failed to fetch POC configs: {exc}") from exc

    def get_poc_config_by_team(self, team: str) -> List[Dict[str, Any]]:
        """
        Get all POC config entries for a given team (case-insensitive).

        Returns:
            List of dictionaries with role, team, access_item, poc_id
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Use COLLATE NOCASE for case-insensitive comparison
                cursor.execute("SELECT * FROM poc_config WHERE LOWER(team) = LOWER(?)", (team,))
                rows = cursor.fetchall()
                configs = [dict(row) for row in rows]
                logger.info("poc_config_fetched", team=team, count=len(configs))
                return configs
        except sqlite3.Error as exc:
            logger.error("poc_config_fetch_failed", team=team, error=str(exc))
            raise UserDBError(f"Failed to fetch POC config: {exc}") from exc

    def insert_poc_config(
        self,
        role: str,
        team: str,
        access_item: str,
        poc_id: str,
    ) -> int:
        """
        Insert a POC config entry.

        Returns:
            The ID of the inserted entry.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO poc_config (role, team, access_item, poc_id)
                    VALUES (?, ?, ?, ?)
                """, (role, team, access_item, poc_id))
                config_id = cursor.lastrowid
                conn.commit()
                logger.info("poc_config_inserted", config_id=config_id, team=team, access_item=access_item)
                return config_id
        except sqlite3.Error as exc:
            logger.error("poc_config_insert_failed", error=str(exc))
            raise UserDBError(f"Failed to insert POC config: {exc}") from exc

    def update_user_status_and_access_items(
        self,
        emailid: str,
        status: Optional[str],
        access_items_updates: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Update user status and access items.

        Args:
            emailid: User email to identify the user
            status: Optional overall user status to update
            access_items_updates: List of dicts with 'item' and 'status' keys

        Returns:
            Updated user data dictionary

        Raises:
            UserDBError: If user not found or item not found in access_items_status
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get current user data
                cursor.execute("SELECT * FROM user WHERE emailid = ?", (emailid,))
                row = cursor.fetchone()
                if row is None:
                    raise UserDBError(f"User with emailid {emailid} not found")
                
                # Convert row to dict
                user_dict = dict(row)
                
                # Parse current access_items_status
                if user_dict.get("access_items_status"):
                    access_items_status = json.loads(user_dict["access_items_status"])
                else:
                    access_items_status = []
                
                # Update access items
                current_timestamp = int(time.time() * 1000)  # Unix timestamp in milliseconds
                for update in access_items_updates:
                    item_name = update.get("item")
                    new_status = update.get("status")
                    
                    if not item_name or not new_status:
                        raise UserDBError("Each access item update must have 'item' and 'status' keys")
                    
                    # Find the item in existing access_items_status
                    item_found = False
                    for item in access_items_status:
                        if item.get("item") == item_name:
                            item["status"] = new_status
                            item["timestamp"] = current_timestamp
                            item_found = True
                            break
                    
                    if not item_found:
                        raise UserDBError(f"Access item '{item_name}' not found in user's access_items_status")
                
                # Update overall status if provided
                new_status_value = status if status is not None else user_dict["status"]
                
                # Save updated data
                access_items_json = json.dumps(access_items_status)
                cursor.execute("""
                    UPDATE user 
                    SET status = ?, access_items_status = ?
                    WHERE emailid = ?
                """, (new_status_value, access_items_json, emailid))
                
                conn.commit()
                
                # Get updated user data to include ai_live_reasoning
                cursor.execute("SELECT * FROM user WHERE emailid = ?", (emailid,))
                updated_row = cursor.fetchone()
                updated_user_dict = dict(updated_row)
                
                # Parse JSON ai_live_reasoning
                if updated_user_dict.get("ai_live_reasoning"):
                    ai_live_reasoning = json.loads(updated_user_dict["ai_live_reasoning"])
                else:
                    ai_live_reasoning = []
                
                # Return updated user data
                updated_user = {
                    "id": updated_user_dict["id"],
                    "name": updated_user_dict["name"],
                    "emailid": updated_user_dict["emailid"],
                    "contact_no": updated_user_dict["contact_no"],
                    "location": updated_user_dict["location"],
                    "date_of_joining": updated_user_dict["date_of_joining"],
                    "level": updated_user_dict["level"],
                    "team": updated_user_dict["team"],
                    "manager": updated_user_dict["manager"],
                    "status": new_status_value,
                    "access_items_status": access_items_status,
                    "ai_live_reasoning": ai_live_reasoning,
                }
                
                logger.info(
                    "user_status_updated",
                    emailid=emailid,
                    status_updated=status is not None,
                    items_updated=len(access_items_updates),
                )
                return updated_user
        except sqlite3.Error as exc:
            logger.error("user_status_update_failed", emailid=emailid, error=str(exc))
            raise UserDBError(f"Failed to update user status: {exc}") from exc

    def update_user_emailid(self, user_id: int, new_emailid: str) -> None:
        """
        Update user email address in the database.

        Args:
            user_id: User ID to identify the user
            new_emailid: New email address to set

        Raises:
            UserDBError: If user not found or database operation fails
        """
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Check if user exists and get current email
                cursor.execute("SELECT id, emailid FROM user WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if row is None:
                    raise UserDBError(f"User with id {user_id} not found")
                
                current_email = row[1] if len(row) > 1 else None
                logger.info(
                    "updating_user_email",
                    user_id=user_id,
                    current_email=current_email,
                    new_email=new_emailid,
                )
                
                # Update email
                cursor.execute(
                    "UPDATE user SET emailid = ? WHERE id = ?",
                    (new_emailid, user_id)
                )
                
                # Verify the update affected a row
                if cursor.rowcount == 0:
                    raise UserDBError(f"Update failed: No rows affected for user_id {user_id}")
                
                # Commit the transaction
                conn.commit()
                
                # Verify the update by querying again
                cursor.execute("SELECT emailid FROM user WHERE id = ?", (user_id,))
                verify_row = cursor.fetchone()
                if verify_row is None:
                    raise UserDBError(f"User with id {user_id} not found after update")
                
                updated_email = verify_row[0]
                if updated_email != new_emailid:
                    logger.error(
                        "email_update_verification_failed",
                        user_id=user_id,
                        expected_email=new_emailid,
                        actual_email=updated_email,
                    )
                    raise UserDBError(
                        f"Email update verification failed. Expected: {new_emailid}, Got: {updated_email}"
                    )
                
                logger.info(
                    "user_email_updated",
                    user_id=user_id,
                    old_email=current_email,
                    new_emailid=new_emailid,
                    verified=True,
                )
            finally:
                conn.close()
        except sqlite3.Error as exc:
            logger.error(
                "user_email_update_failed",
                user_id=user_id,
                new_emailid=new_emailid,
                error=str(exc),
            )
            raise UserDBError(f"Failed to update user email: {exc}") from exc

    def delete_user_by_id(self, user_id: int) -> None:
        """
        Delete a user by ID from the database.

        Args:
            user_id: ID of the user to delete

        Raises:
            UserDBError: If user not found or database operation fails
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute("SELECT id FROM user WHERE id = ?", (user_id,))
                if cursor.fetchone() is None:
                    raise UserDBError(f"User with id {user_id} not found")
                
                # Delete user
                cursor.execute("DELETE FROM user WHERE id = ?", (user_id,))
                conn.commit()
                
                logger.info("user_deleted", user_id=user_id)
        except sqlite3.Error as exc:
            logger.error("user_delete_failed", user_id=user_id, error=str(exc))
            raise UserDBError(f"Failed to delete user: {exc}") from exc

    def delete_email_by_name(self, name: str) -> Dict[str, Any]:
        """
        Delete email address for a user by name (case-insensitive).
        Sets emailid to empty string.

        Args:
            name: User name to identify the user

        Returns:
            Updated user data dictionary

        Raises:
            UserDBError: If user not found or database operation fails
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Find user by name (case-insensitive)
                cursor.execute("SELECT * FROM user WHERE LOWER(name) = LOWER(?)", (name,))
                row = cursor.fetchone()
                
                if row is None:
                    raise UserDBError(f"User with name '{name}' not found")
                
                # Convert row to dict
                user_dict = dict(row)
                user_id = user_dict["id"]
                
                # Update email to empty string
                cursor.execute(
                    "UPDATE user SET emailid = ? WHERE id = ?",
                    ("", user_id)
                )
                conn.commit()
                
                # Get updated user data
                cursor.execute("SELECT * FROM user WHERE id = ?", (user_id,))
                updated_row = cursor.fetchone()
                updated_user_dict = dict(updated_row)
                
                # Parse JSON access_items_status
                if updated_user_dict.get("access_items_status"):
                    updated_user_dict["access_items_status"] = json.loads(updated_user_dict["access_items_status"])
                else:
                    updated_user_dict["access_items_status"] = []
                # Parse JSON ai_live_reasoning
                if updated_user_dict.get("ai_live_reasoning"):
                    updated_user_dict["ai_live_reasoning"] = json.loads(updated_user_dict["ai_live_reasoning"])
                else:
                    updated_user_dict["ai_live_reasoning"] = []
                
                logger.info(
                    "user_email_deleted_by_name",
                    name=name,
                    user_id=user_id,
                    previous_email=user_dict.get("emailid"),
                )
                
                return updated_user_dict
        except sqlite3.Error as exc:
            logger.error(
                "user_email_delete_by_name_failed",
                name=name,
                error=str(exc),
            )
            raise UserDBError(f"Failed to delete email for user '{name}': {exc}") from exc

    def append_ai_live_reasoning(
        self,
        message: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
    ) -> None:
        """
        Append a one-liner message with timestamp to user's ai_live_reasoning array.
        
        Args:
            message: One-liner message describing what the agent is doing
            user_id: User ID to identify the user (preferred)
            user_email: User email to identify the user (if user_id not provided)
            
        Raises:
            UserDBError: If user not found or database operation fails
        """
        try:
            conn = self.get_connection()
            try:
                # Set row factory to get dict-like access
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Find user by ID or email
                user_dict = None
                if user_id:
                    cursor.execute("SELECT * FROM user WHERE id = ?", (user_id,))
                    row = cursor.fetchone()
                    if row:
                        user_dict = dict(row)
                elif user_email:
                    cursor.execute("SELECT * FROM user WHERE emailid = ?", (user_email,))
                    row = cursor.fetchone()
                    if row:
                        user_dict = dict(row)
                
                if not user_dict:
                    identifier = f"ID {user_id}" if user_id else f"email {user_email}"
                    raise UserDBError(f"User with {identifier} not found")
                
                # Get current ai_live_reasoning
                current_reasoning = []
                if user_dict.get("ai_live_reasoning"):
                    try:
                        current_reasoning = json.loads(user_dict["ai_live_reasoning"])
                    except (json.JSONDecodeError, TypeError):
                        current_reasoning = []
                
                # Add new entry with timestamp
                timestamp = int(time.time() * 1000)  # Unix timestamp in milliseconds
                new_entry = {
                    "message": message,
                    "timestamp": timestamp,
                }
                current_reasoning.append(new_entry)
                
                # Update database
                reasoning_json = json.dumps(current_reasoning)
                if user_id:
                    cursor.execute(
                        "UPDATE user SET ai_live_reasoning = ? WHERE id = ?",
                        (reasoning_json, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE user SET ai_live_reasoning = ? WHERE emailid = ?",
                        (reasoning_json, user_email)
                    )
                
                conn.commit()
                
                logger.info(
                    "ai_live_reasoning_appended",
                    user_id=user_dict.get("id"),
                    user_email=user_dict.get("emailid"),
                    message=message,
                    total_entries=len(current_reasoning),
                )
            finally:
                conn.close()
        except sqlite3.Error as exc:
            logger.error(
                "ai_live_reasoning_append_failed",
                user_id=user_id,
                user_email=user_email,
                error=str(exc),
            )
            raise UserDBError(f"Failed to append ai_live_reasoning: {exc}") from exc

