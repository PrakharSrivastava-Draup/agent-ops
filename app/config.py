from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseSettings, Field


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="planning_llm")
    app_secret_key: str = Field(..., env="APP_SECRET_KEY")
    github_token: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = Field(default=None, env="AWS_SESSION_TOKEN")
    jira_base_url: Optional[str] = Field(default=None, env="JIRA_BASE_URL")
    jira_username: Optional[str] = Field(default=None, env="JIRA_USERNAME")
    jira_api_token: Optional[str] = Field(default=None, env="JIRA_API_TOKEN")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    cursor_api_key: Optional[str] = Field(default=None, env="CURSOR_API_KEY")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    # Jenkins configuration
    aws_region: str = Field(default="us-east-2", env="AWS_REGION")
    jenkins_ssm_parameter: str = Field(default="jenkins", env="JENKINS_SSM_PARAMETER")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    return Settings()


