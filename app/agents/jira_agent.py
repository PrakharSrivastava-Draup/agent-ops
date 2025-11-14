from __future__ import annotations

import asyncio
from typing import Any

from jira import JIRA
from jira.exceptions import JIRAError

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.utils.sanitization import sanitize_jql, validate_issue_key


class JiraAgent(BaseAgent):
    """Read-only JIRA agent."""

    def __init__(self, base_url: str | None, username: str | None, api_token: str | None) -> None:
        if not base_url:
            raise ValueError("JIRA_BASE_URL must be configured for JiraAgent.")
        super().__init__("JiraAgent")
        options = {"server": base_url}
        auth = None
        if username and api_token:
            auth = (username, api_token)
        self.client = JIRA(options=options, basic_auth=auth)
        self._log_info("Initialized JIRA agent", base_url=base_url)

    async def get_issue(self, issue_key: str) -> AgentResponse:
        """Return issue details with limited comments."""
        validate_issue_key(issue_key)

        def _fetch() -> dict[str, Any]:
            issue = self.client.issue(issue_key, fields="summary,description,reporter,status,comment")
            comments = issue.fields.comment.comments if hasattr(issue.fields, "comment") else []
            comment_summaries = [
                {
                    "author": comment.author.displayName,
                    "body": comment.body,
                    "created": comment.created,
                }
                for comment in comments[:10]
            ]
            return {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description,
                "reporter": getattr(issue.fields.reporter, "displayName", None),
                "status": getattr(issue.fields.status, "name", None),
                "comments": comment_summaries,
            }

        try:
            data = await asyncio.to_thread(_fetch)
        except JIRAError as exc:
            self._log_error("Failed to fetch issue", issue_key=issue_key, error=str(exc))
            raise AgentError("Failed to fetch Jira issue.") from exc
        return AgentResponse(data=data)

    async def search_issues(self, jql: str, limit: int = 20) -> AgentResponse:
        """Return issues matching JQL query."""
        sanitize_jql(jql)
        limit = max(1, min(limit, 50))

        def _search() -> list[dict[str, Any]]:
            issues = self.client.search_issues(jql, maxResults=limit, fields="summary,status")
            return [
                {
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": getattr(issue.fields.status, "name", None),
                }
                for issue in issues
            ]

        try:
            results = await asyncio.to_thread(_search)
        except JIRAError as exc:
            self._log_error("Failed to search issues", error=str(exc))
            raise AgentError("Failed to search Jira issues.") from exc
        return AgentResponse(data={"issues": results})


