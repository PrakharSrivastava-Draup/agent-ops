from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx  # type: ignore
from httpx import HTTPStatusError  # type: ignore
from tenacity import (  # type: ignore
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.utils.sanitization import (
    sanitize_path,
    validate_branch_name,
    validate_owner_name,
    validate_repo_name,
)


class GithubAgent(BaseAgent):
    """Read-only GitHub agent using REST API."""

    BASE_URL = "https://api.github.com"
    MAX_PATCH_LENGTH = 4_000
    MAX_FILE_CONTENT = 40_000

    def __init__(self, token: str | None, timeout: float = 10.0) -> None:
        super().__init__("GithubAgent")
        self.token = token
        self.timeout = timeout
        self._log_info("Initialized GitHub agent", has_token=bool(token))

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.BASE_URL}{path}"
        self._log_debug("GitHub request", method=method, url=url, params=params)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((HTTPStatusError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json()
        raise AgentError("GitHub request failed after retries.")

    async def get_pr(self, owner: str, repo: str, number: int) -> AgentResponse:
        """Return pull request details with truncated patch content."""
        validate_owner_name(owner)
        validate_repo_name(repo)
        if number <= 0:
            raise ValueError("PR number must be positive.")

        pr_data_task = asyncio.create_task(
            self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        )
        files_task = asyncio.create_task(
            self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}/files", params={"per_page": 100})
        )

        try:
            pr_data, files_data = await asyncio.gather(pr_data_task, files_task)
        except (HTTPStatusError, httpx.HTTPError, RetryError) as exc:
            self._log_error("Failed to fetch PR", owner=owner, repo=repo, number=number, error=str(exc))
            raise AgentError("Failed to fetch pull request details.") from exc

        truncated = False
        file_summaries: list[dict[str, Any]] = []

        for file_info in files_data:
            patch = file_info.get("patch")
            is_truncated = False
            if patch and len(patch) > self.MAX_PATCH_LENGTH:
                patch = f"{patch[: self.MAX_PATCH_LENGTH]}\\n...TRUNCATED..."
                is_truncated = True
                truncated = True
            file_summaries.append(
                {
                    "filename": file_info.get("filename"),
                    "status": file_info.get("status"),
                    "additions": file_info.get("additions"),
                    "deletions": file_info.get("deletions"),
                    "changes": file_info.get("changes"),
                    "patch": patch,
                    "truncated": is_truncated,
                }
            )

        data = {
            "title": pr_data.get("title"),
            "author": pr_data.get("user", {}).get("login"),
            "body": pr_data.get("body"),
            "changed_files": [info.get("filename") for info in files_data if info.get("filename")],
            "files": file_summaries,
        }
        return AgentResponse(data=data, truncated=truncated)

    async def list_recent_commits(
        self, owner: str, repo: str, branch: str, limit: int = 20
    ) -> AgentResponse:
        """List recent commits for a branch."""
        validate_owner_name(owner)
        validate_repo_name(repo)
        validate_branch_name(branch)
        limit = max(1, min(limit, 50))
        params = {"sha": branch, "per_page": limit}

        try:
            commits = await self._request(
                "GET", f"/repos/{owner}/{repo}/commits", params=params
            )
        except (HTTPStatusError, httpx.HTTPError, RetryError) as exc:
            self._log_error(
                "Failed to list commits",
                owner=owner,
                repo=repo,
                branch=branch,
                error=str(exc),
            )
            raise AgentError("Failed to list recent commits.") from exc

        parsed = [
            {
                "sha": commit.get("sha"),
                "message": commit.get("commit", {}).get("message"),
                "author": commit.get("commit", {}).get("author", {}).get("name"),
                "date": commit.get("commit", {}).get("author", {}).get("date"),
            }
            for commit in commits
        ]
        return AgentResponse(data={"commits": parsed})

    async def get_file(
        self, owner: str, repo: str, path: str, ref: str
    ) -> AgentResponse:
        """Return repository file content up to a safe length."""
        validate_owner_name(owner)
        validate_repo_name(repo)
        sanitize_path(path)
        validate_branch_name(ref)

        try:
            response = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": ref},
            )
        except (HTTPStatusError, httpx.HTTPError, RetryError) as exc:
            self._log_error(
                "Failed to fetch file",
                owner=owner,
                repo=repo,
                path=path,
                ref=ref,
                error=str(exc),
            )
            raise AgentError("Failed to fetch file content.") from exc

        if isinstance(response, list):
            raise AgentError("Requested path is a directory, not a file.")

        content = response.get("content")
        encoding = response.get("encoding")
        if encoding != "base64" or content is None:
            raise AgentError("Unexpected file encoding.")

        try:
            decoded_bytes = base64.b64decode(content, validate=True)
        except (ValueError, TypeError) as exc:
            raise AgentError("Failed to decode file content.") from exc
        text = decoded_bytes.decode("utf-8", errors="replace")
        truncated = False
        if len(text) > self.MAX_FILE_CONTENT:
            text = text[: self.MAX_FILE_CONTENT] + "\n...TRUNCATED..."
            truncated = True

        data = {
            "path": response.get("path"),
            "sha": response.get("sha"),
            "size": response.get("size"),
            "content": text,
            "encoding": "utf-8",
        }
        return AgentResponse(data=data, truncated=truncated)

