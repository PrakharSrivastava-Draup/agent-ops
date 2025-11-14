"""
API routes for user management operations.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_app_settings
from app.config import Settings
from app.models.schemas import (
    AccessItemStatus,
    OnboardUserRequest,
    POCConfigEntry,
    UserResponse,
)
from app.services.user_db import UserDB
from app.services.user_service import UserService, UserServiceError
from app.utils.logging import get_logger

logger = get_logger("user_routes")

router = APIRouter()


def get_user_db(settings: Settings = Depends(get_app_settings)) -> UserDB:
    """Create and return UserDB instance."""
    return UserDB(db_path=settings.user_db_path)


def get_user_service(db: UserDB = Depends(get_user_db)) -> UserService:
    """Create and return UserService instance."""
    return UserService(db=db)


@router.post("/onboard_user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def onboard_user(
    request: OnboardUserRequest,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Onboard a new user.

    Fetches POC config entries for the user's team, builds access_items_status
    with default 'pending' status, and creates a new user record with status='new'.

    Request body:
    - name: User's name
    - emailid: User's email address
    - contact_no: Contact number
    - location: Location
    - date_of_joining: Date of joining (ISO date string)
    - level: User level
    - team: Team name
    - manager: Manager name

    Returns:
        UserResponse with all user data including generated ID and access_items_status.
    """
    try:
        user_data = user_service.onboard_user(
            name=request.name,
            emailid=request.emailid,
            contact_no=request.contact_no,
            location=request.location,
            date_of_joining=request.date_of_joining,
            level=request.level,
            team=request.team,
            manager=request.manager,
        )

        # Convert access_items_status to AccessItemStatus objects
        access_items = [
            AccessItemStatus(**item) for item in user_data["access_items_status"]
        ]

        return UserResponse(
            id=user_data["id"],
            name=user_data["name"],
            emailid=user_data["emailid"],
            contact_no=user_data["contact_no"],
            location=user_data["location"],
            date_of_joining=user_data["date_of_joining"],
            level=user_data["level"],
            team=user_data["team"],
            manager=user_data["manager"],
            status=user_data["status"],
            access_items_status=access_items,
        )
    except UserServiceError as exc:
        logger.error("onboard_user_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to onboard user: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during user onboarding.",
        ) from exc


@router.get("/status_all", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
async def status_all(
    user_service: UserService = Depends(get_user_service),
) -> List[UserResponse]:
    """
    Get all users and their current status.

    Returns:
        List of UserResponse objects with all user data including access_items_status.
    """
    try:
        users = user_service.get_all_users()
        result = []
        for user in users:
            # Convert access_items_status to AccessItemStatus objects
            access_items = [
                AccessItemStatus(**item) for item in user.get("access_items_status", [])
            ]
            result.append(
                UserResponse(
                    id=user["id"],
                    name=user["name"],
                    emailid=user["emailid"],
                    contact_no=user["contact_no"],
                    location=user["location"],
                    date_of_joining=user["date_of_joining"],
                    level=user["level"],
                    team=user["team"],
                    manager=user["manager"],
                    status=user["status"],
                    access_items_status=access_items,
                )
            )
        return result
    except UserServiceError as exc:
        logger.error("status_all_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve users: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving users.",
        ) from exc


@router.get("/poc_config", status_code=status.HTTP_200_OK)
async def get_poc_config(
    user_service: UserService = Depends(get_user_service),
) -> List[dict]:
    """
    Get all POC configuration entries.

    Returns:
        List of POC config dictionaries with id, role, team, access_item, poc_id.
    """
    try:
        configs = user_service.get_all_poc_configs()
        return configs
    except UserServiceError as exc:
        logger.error("get_poc_config_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve POC config: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving POC config.",
        ) from exc


@router.post("/add_poc_config", status_code=status.HTTP_201_CREATED)
async def add_poc_config(
    request: List[POCConfigEntry],
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """
    Add POC configuration entries.

    For each entry, creates one database row per access_item (denormalized).

    Request body:
        List of POCConfigEntry objects with:
        - role: Role name
        - team: Team name
        - access_items: List of access item names
        - poc_id: POC email or unique reference

    Returns:
        Dictionary with success status and count of inserted rows.
    """
    try:
        # Convert POCConfigEntry objects to dictionaries
        config_entries = [
            {
                "role": entry.role,
                "team": entry.team,
                "access_items": entry.access_items,
                "poc_id": entry.poc_id,
            }
            for entry in request
        ]

        inserted_ids = user_service.add_poc_config(config_entries)
        return {
            "success": True,
            "message": f"Inserted {len(inserted_ids)} POC config entries",
            "inserted_ids": inserted_ids,
        }
    except UserServiceError as exc:
        logger.error("add_poc_config_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add POC config: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding POC config.",
        ) from exc

