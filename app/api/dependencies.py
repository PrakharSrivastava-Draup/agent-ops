from functools import lru_cache
from typing import Dict

from fastapi import Depends, HTTPException, status

from app.agents import AWSAgent, BaseAgent, GithubAgent, JenkinsAgent, JiraAgent
from app.config import Settings, get_settings
from app.services.jenkins_service import JenkinsService
from app.services.llm_client import LLMClient
from app.services.llm_planner import LLMPlanner
from app.services.orchestrator import TaskOrchestrator
from app.services.plan_validator import PlanValidator
from app.utils.logging import get_logger


logger = get_logger("dependencies")


def get_app_settings() -> Settings:
    """Dependency for retrieving app settings."""
    try:
        return get_settings()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("settings_load_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load application settings.",
        ) from exc


@lru_cache(maxsize=1)
def _cached_llm_client(api_key: str) -> LLMClient:
    return LLMClient(api_key=api_key)


def get_llm_client(settings: Settings = Depends(get_app_settings)) -> LLMClient:
    """Provide a cached LLM client."""
    api_key = settings.openai_api_key or settings.cursor_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No LLM API key configured.",
        )
    return _cached_llm_client(api_key)


@lru_cache(maxsize=1)
def _cached_agents(
    github_token: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_session_token: str | None,
    aws_region: str,
    jenkins_ssm_parameter: str,
    jira_base_url: str | None,
    jira_username: str | None,
    jira_api_token: str | None,
) -> Dict[str, BaseAgent]:
    agents: Dict[str, BaseAgent] = {
        "GithubAgent": GithubAgent(github_token),
        "AWSAgent": AWSAgent(aws_access_key_id, aws_secret_access_key),
    }
    
    # Initialize JiraAgent if configured
    if jira_base_url:
        try:
            agents["JiraAgent"] = JiraAgent(jira_base_url, jira_username, jira_api_token)
        except ValueError:
            # JiraAgent requires all config, skip if not available
            pass
    
    # Initialize JenkinsAgent
    jenkins_service = JenkinsService(
        aws_region=aws_region,
        ssm_parameter_name=jenkins_ssm_parameter,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )
    agents["JenkinsAgent"] = JenkinsAgent(jenkins_service=jenkins_service)
    
    return agents


def get_agents(settings: Settings = Depends(get_app_settings)) -> Dict[str, BaseAgent]:
    """Instantiate access agents."""
    try:
        return _cached_agents(
            settings.github_token,
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            getattr(settings, "aws_session_token", None),
            settings.aws_region,
            settings.jenkins_ssm_parameter,
            settings.jira_base_url,
            settings.jira_username,
            settings.jira_api_token,
        )
    except Exception as exc:
        logger.error("agent_initialization_failed", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize agents.",
        ) from exc


@lru_cache(maxsize=1)
def get_plan_validator() -> PlanValidator:
    return PlanValidator()


@lru_cache(maxsize=1)
def _cached_planner(api_key: str) -> LLMPlanner:
    client = _cached_llm_client(api_key)
    return LLMPlanner(client=client)


def get_orchestrator(
    settings: Settings = Depends(get_app_settings),
    agents: Dict[str, BaseAgent] = Depends(get_agents),
    validator: PlanValidator = Depends(get_plan_validator),
) -> TaskOrchestrator:
    api_key = settings.openai_api_key or settings.cursor_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No LLM API key configured.",
        )
    planner = _cached_planner(api_key)
    return TaskOrchestrator(planner=planner, validator=validator, agents=agents)

