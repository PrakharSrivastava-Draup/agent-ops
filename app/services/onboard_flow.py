"""
Background service for handling agentic onboarding flow after user creation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from app.models.schemas import TaskRequest
from app.services.orchestrator import TaskOrchestrator
from app.services.user_db import UserDB
from app.services.user_service import UserServiceError
from app.utils.logging import get_logger

logger = get_logger("onboard_flow")

# Valid services for Jenkins (must match JenkinsAgent.VALID_SERVICES)
VALID_JENKINS_SERVICES = {"AWS", "GitHub", "Confluence", "Database"}

# Service name mapping (case-insensitive to case-sensitive)
SERVICE_NAME_MAP = {
    "aws": "AWS",
    "github": "GitHub",
    "confluence": "Confluence",
    "database": "Database",
}


def map_to_jenkins_services(access_items: List[Dict[str, Any]]) -> List[str]:
    """
    Map access items to Jenkins service names (case-insensitive match).
    
    Only includes items with status="pending" that match valid Jenkins services.
    Returns exact case-sensitive service names for Jenkins.
    
    Args:
        access_items: List of access item dictionaries with 'item' and 'status' keys
        
    Returns:
        List of case-sensitive service names (AWS, GitHub, Confluence, Database)
    """
    valid_services = []
    
    for item in access_items:
        item_name = item.get("item", "").strip()
        item_status = item.get("status", "").strip().lower()
        
        # Only process pending items
        if item_status != "pending":
            continue
        
        # Normalize item name (lowercase for matching)
        item_name_lower = item_name.lower()
        
        # Check if it matches any valid service (case-insensitive)
        if item_name_lower in SERVICE_NAME_MAP:
            jenkins_service = SERVICE_NAME_MAP[item_name_lower]
            valid_services.append(jenkins_service)
            logger.info(
                "access_item_mapped_to_jenkins_service",
                access_item=item_name,
                jenkins_service=jenkins_service,
            )
    
    # Remove duplicates and sort for consistency
    unique_services = sorted(list(set(valid_services)))
    
    logger.info(
        "mapped_access_items_to_jenkins_services",
        access_items_count=len(access_items),
        valid_services_count=len(unique_services),
        services=unique_services,
    )
    
    return unique_services


async def execute_onboard_flow(
    user_id: int,
    user_name: str,
    orchestrator: TaskOrchestrator,
    user_db_path: str,
) -> None:
    """
    Execute the agentic onboarding flow for a user.
    
    Flow:
    1. Wait 5 seconds
    2. Generate email using EntraAgent and save to DB
    3. Wait another 5 seconds
    4. Fetch user's access_items_status
    5. Filter for pending items matching valid services
    6. Trigger JenkinsAgent if any valid pending services found
    
    Args:
        user_id: ID of the user to onboard
        user_name: Name of the user
        orchestrator: TaskOrchestrator instance
        user_db_path: Path to the user database
    """
    try:
        logger.info(
            "onboard_flow_started",
            user_id=user_id,
            user_name=user_name,
        )
        
        # Step 1: Wait 5 seconds
        logger.info("onboard_flow_waiting_5_seconds_for_email_generation")
        await asyncio.sleep(5)
        
        # Step 2: Generate email using EntraAgent and save to DB
        try:
            logger.info(
                "onboard_flow_generating_email",
                user_id=user_id,
                user_name=user_name,
            )
            
            # Create task request for EntraAgent
            task_request = TaskRequest(
                task=f"Generate and save email for user with name {user_name}",
                context={"name": user_name},
            )
            
            # Execute via orchestrator
            entra_response = await orchestrator.execute(task_request)
            
            logger.info(
                "onboard_flow_email_generated",
                user_id=user_id,
                request_id=str(entra_response.request_id),
                success=len(entra_response.warnings) == 0,
                warnings=entra_response.warnings,
            )
            
        except Exception as e:
            logger.error(
                "onboard_flow_email_generation_failed",
                user_id=user_id,
                user_name=user_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue with flow even if email generation fails
        
        # Step 3: Wait another 5 seconds
        logger.info("onboard_flow_waiting_5_seconds_before_jenkins_check")
        await asyncio.sleep(5)
        
        # Step 4: Fetch user's access_items_status
        try:
            user_db = UserDB(db_path=user_db_path)
            all_users = user_db.get_all_users()
            
            user = None
            for u in all_users:
                if u.get("id") == user_id:
                    user = u
                    break
            
            if not user:
                logger.error(
                    "onboard_flow_user_not_found",
                    user_id=user_id,
                )
                return
            
            access_items_status = user.get("access_items_status", [])
            user_email = user.get("emailid", "")
            
            logger.info(
                "onboard_flow_user_fetched",
                user_id=user_id,
                email=user_email,
                access_items_count=len(access_items_status),
            )
            
        except Exception as e:
            logger.error(
                "onboard_flow_fetch_user_failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return
        
        # Step 5: Filter for pending items matching valid services
        valid_services = map_to_jenkins_services(access_items_status)
        
        # Step 6: Trigger JenkinsAgent if any valid pending services found
        if not valid_services:
            logger.info(
                "onboard_flow_no_valid_pending_services",
                user_id=user_id,
                access_items_count=len(access_items_status),
            )
            return
        
        # User must have email for Jenkins onboarding
        if not user_email:
            logger.warning(
                "onboard_flow_no_email_for_jenkins",
                user_id=user_id,
                valid_services=valid_services,
            )
            return
        
        try:
            logger.info(
                "onboard_flow_triggering_jenkins",
                user_id=user_id,
                user_email=user_email,
                services=valid_services,
            )
            
            # Create task request for JenkinsAgent
            task_request = TaskRequest(
                task=f"Onboard {user_email} with access to {', '.join(valid_services)}",
                context={
                    "user_email": user_email,
                    "services": valid_services,
                },
            )
            
            # Execute via orchestrator
            jenkins_response = await orchestrator.execute(task_request)
            
            logger.info(
                "onboard_flow_jenkins_triggered",
                user_id=user_id,
                request_id=str(jenkins_response.request_id),
                success=len(jenkins_response.warnings) == 0,
                warnings=jenkins_response.warnings,
            )
            
        except Exception as e:
            logger.error(
                "onboard_flow_jenkins_trigger_failed",
                user_id=user_id,
                user_email=user_email,
                services=valid_services,
                error=str(e),
                error_type=type(e).__name__,
            )
        
        logger.info(
            "onboard_flow_completed",
            user_id=user_id,
            user_name=user_name,
        )
        
    except Exception as e:
        logger.error(
            "onboard_flow_unexpected_error",
            user_id=user_id,
            user_name=user_name,
            error=str(e),
            error_type=type(e).__name__,
        )

