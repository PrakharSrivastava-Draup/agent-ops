"""
API routes for user management operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_app_settings
from app.config import Settings
from app.models.schemas import (
    AccessItemStatus,
    OnboardUserRequest,
    POCConfigEntry,
    UpdateUserStatusRequest,
    UserResponse,
)
from app.services.user_db import UserDB
from app.services.user_service import UserService, UserServiceError
from app.utils.logging import get_logger

logger = get_logger("user_routes")

router = APIRouter()


class UserDetailsPayload(BaseModel):
    """Payload structure for user_details in the new format."""
    contactNo: str
    doj: str
    email: str
    fullName: str
    level: str
    location: str
    team: str


class OnboardUserPayload(BaseModel):
    """New payload structure with msalData and user_details."""
    msalData: Optional[Dict[str, Any]] = None
    user_details: UserDetailsPayload


def parse_onboard_payload(payload: OnboardUserPayload) -> OnboardUserRequest:
    """
    Parse the new payload structure and map to existing OnboardUserRequest.
    
    Maps:
    - user_details.fullName -> name
    - user_details.email -> emailid
    - user_details.contactNo -> contact_no
    - user_details.location -> location
    - user_details.doj -> date_of_joining
    - user_details.level -> level
    - user_details.team -> team
    - manager -> extracted from msalData or set to empty string
    """
    user_details = payload.user_details
    
    # Extract manager from msalData if available, otherwise use empty string
    manager = ""
    if payload.msalData:
        # Try common fields where manager might be stored
        manager = (
            payload.msalData.get("manager") or
            payload.msalData.get("managerName") or
            payload.msalData.get("managerEmail") or
            payload.msalData.get("reportsTo") or
            ""
        )
    
    return OnboardUserRequest(
        name=user_details.fullName,
        emailid=user_details.email,
        contact_no=user_details.contactNo,
        location=user_details.location,
        date_of_joining=user_details.doj,
        level=user_details.level,
        team=user_details.team,
        manager=manager,
    )


def get_user_db(settings: Settings = Depends(get_app_settings)) -> UserDB:
    """Create and return UserDB instance."""
    return UserDB(db_path=settings.user_db_path)


def get_user_service(db: UserDB = Depends(get_user_db)) -> UserService:
    """Create and return UserService instance."""
    return UserService(db=db)


@router.post("/onboard_user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def onboard_user(
    payload: OnboardUserPayload = Body(...),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Onboard a new user.

    Accepts payload in the format:
    {
        "msalData": {...},
        "user_details": {
            "contactNo": "12e1",
            "doj": "2025-11-15",
            "email": "vikas@draup.com",
            "fullName": "vikas",
            "level": "SDE 1",
            "location": "Bengalore, Karnataka, India",
            "team": "Frontend"
        }
    }

    Fetches POC config entries for the user's team, builds access_items_status
    with default 'pending' status, and creates a new user record with status='new'.

    Returns:
        UserResponse with all user data including generated ID and access_items_status.
    """
    try:
        # Parse the new payload structure to existing format
        request = parse_onboard_payload(payload)
        
        logger.info(
            "onboard_user_received",
            email=request.emailid,
            name=request.name,
            team=request.team,
            has_msal_data=payload.msalData is not None,
        )
        
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


@router.put("/update_status", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_status(
    request: UpdateUserStatusRequest,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Update user status and access items.

    Request body:
        {
            "emailid": "user@example.com",
            "status": "in_progress",  # Optional: overall user status
            "access_items_status": [
                {"item": "AWS", "status": "in progress"},
                {"item": "GitHub", "status": "completed"}
            ]
        }

    Valid access item statuses: "pending", "in progress", "completed"

    Returns:
        UserResponse with updated user data including status and access_items_status.

    Raises:
        404: If user not found or access item not found in user's access_items_status
        400: If invalid status value provided
    """
    try:
        logger.info(
            "update_status_received",
            emailid=request.emailid,
            status_provided=request.status is not None,
            items_count=len(request.access_items_status),
        )

        user_data = user_service.update_user_status(
            emailid=request.emailid,
            status=request.status,
            access_items_status=request.access_items_status,
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
        error_msg = str(exc)
        logger.error("update_status_failed", emailid=request.emailid, error=error_msg)
        
        # Determine appropriate status code based on error message
        if "not found" in error_msg.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "invalid" in error_msg.lower():
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        raise HTTPException(
            status_code=status_code,
            detail=error_msg,
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating user status.",
        ) from exc

