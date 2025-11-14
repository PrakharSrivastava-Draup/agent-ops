"""
API routes for Entra ID (Azure AD) operations.
"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_app_settings
from app.config import Settings, get_settings
from app.services.entra_service import EntraServiceError
from app.services.user_db import UserDB, UserDBError
from app.services.user_service import UserService, UserServiceError
from app.utils.logging import get_logger

logger = get_logger("entra_routes")

router = APIRouter()


class GenerateEmailRequest(BaseModel):
    """Request model for Entra email generation endpoint."""
    
    user_name: str


def get_user_db(settings: Settings = Depends(get_app_settings)) -> UserDB:
    """Create and return UserDB instance."""
    return UserDB(db_path=settings.user_db_path)


def get_user_service(db: UserDB = Depends(get_user_db)) -> UserService:
    """Create and return UserService instance."""
    return UserService(db=db)


@router.post("/generate_email", status_code=status.HTTP_200_OK)
async def generate_company_email(
    request: GenerateEmailRequest = Body(...),
    user_service: UserService = Depends(get_user_service),
) -> Dict[str, str]:
    """
    Generate a company email address for a user and create user in Entra ID.

    Args:
        request: Request body with user_name

    Returns:
        dict: Response with generated email address

    Raises:
        400: If multiple users found with the same name
        400: If user already has an email address
        500: If Entra service fails or database operation fails

    Example:
        POST /api/entra/generate_email
        Body: {
            "user_name": "John Doe"
        }
    """
    try:
        user_name = request.user_name.strip()
        if not user_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_name cannot be empty",
            )

        logger.info("generate_email_request_received", user_name=user_name)

        # Get users by name
        users = user_service.db.get_users_by_name(user_name)

        # Check if multiple users found
        if len(users) > 1:
            logger.warning(
                "multiple_users_found",
                user_name=user_name,
                count=len(users),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Multiple users found with name '{user_name}'. Please use a more specific identifier.",
            )

        # Check if no user found
        if len(users) == 0:
            logger.warning("no_user_found", user_name=user_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No user found with name '{user_name}'.",
            )

        # Get the single user
        user = users[0]
        user_id = user["id"]
        existing_email = user.get("emailid", "")

        # Check if email already exists
        if existing_email and existing_email.strip():
            logger.warning(
                "user_already_has_email",
                user_name=user_name,
                user_id=user_id,
                existing_email=existing_email,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{user_name}' already has an email address: {existing_email}",
            )

        # Extract firstname and lastname from user name
        name_parts = user_name.strip().split()
        if len(name_parts) < 2:
            # If only one name part, use it as both first and last name
            firstname = name_parts[0] if name_parts else "User"
            lastname = name_parts[0] if name_parts else "User"
        else:
            # First part is firstname, rest is lastname
            firstname = name_parts[0]
            lastname = " ".join(name_parts[1:])

        logger.info(
            "generating_email_for_user",
            user_name=user_name,
            user_id=user_id,
            firstname=firstname,
            lastname=lastname,
        )

        # Generate company email and update user in database
        settings = get_settings()
        generated_email = user_service.generate_and_update_email(
            user_id=user_id,
            firstname=firstname,
            lastname=lastname,
            full_name=user_name,
            settings=settings,
        )

        logger.info(
            "email_generated_successfully",
            user_name=user_name,
            user_id=user_id,
            generated_email=generated_email,
        )

        return {"email": generated_email}

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except EntraServiceError as e:
        logger.error("entra_email_generation_failed", user_name=request.user_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate company email: {str(e)}",
        ) from e
    except UserServiceError as e:
        logger.error("user_service_error", user_name=request.user_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user email: {str(e)}",
        ) from e
    except UserDBError as e:
        logger.error("user_db_error", user_name=request.user_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(
            "unexpected_error",
            user_name=request.user_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating company email.",
        ) from e

