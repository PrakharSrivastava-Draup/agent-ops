# Minimal Agentic System

A prototype-ready FastAPI service that implements a minimal agentic system: one **planning LLM** that orchestrates multiple **access agents** (GitHub, AWS, JIRA). The planning LLM issues actions to the access agents; access agents are simple tool wrappers that call external APIs. The system performs read-only operations and returns structured plans, execution traces, and synthesized results.

## Overview

- **Purpose**: Accept a high-level request (JSON) describing a task related to code/repo/infra/tickets. The planning LLM (single LLM) will plan a sequence of tool calls and instruct the access agents (GitHubAgent, AWSAgent, JiraAgent) to perform read-only operations. The API returns a structured plan, the tool call trace, and the final aggregated result produced by the planning LLM after receiving tool outputs.
- **Operations**: All operations are read-only. The system does not write to external systems (no creating issues, commits, pushes, or modifying infra). If a write is implied, the planning LLM should return a suggested action but not call any write API.
- **Architecture**: Simple and clear implementation prioritizing readability and modularity.

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- httpx for HTTP requests
- python-dotenv for env loading
- direct GitHub REST via httpx
- boto3 for AWS read-only operations (e.g., list S3 buckets, describe instances)
- jira (jira-python) or direct REST calls for JIRA read operations
- OpenAI Python SDK (or abstract LLM client supporting alternative providers via env)
- pydantic for schemas
- structlog for structured logging

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Required
APP_SECRET_KEY=replace-with-random-string
GITHUB_TOKEN=replace-with-github-token

# Optional - AWS (read-only)
AWS_ACCESS_KEY_ID=optional-readonly-key
AWS_SECRET_ACCESS_KEY=optional-readonly-secret

# Optional - JIRA (read-only)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=jira-user@example.com
JIRA_API_TOKEN=jira-api-token

# Optional - LLM Provider (at least one required)
OPENAI_API_KEY=optional-openai-api-key
CURSOR_API_KEY=optional-cursor-api-key

# Optional - Logging
LOG_LEVEL=INFO
```

### Notes:

- **APP_SECRET_KEY**: Random string for app use (required)
- **GITHUB_TOKEN**: Read-only token for GitHub API (required)
- **AWS credentials**: Optional, can rely on local AWS config if not provided
- **JIRA credentials**: All three (base URL, username, API token) must be provided if JIRA is used
- **LLM API Key**: At least one of `OPENAI_API_KEY` or `CURSOR_API_KEY` must be provided

## Installation

1. **Clone the repository** (if applicable)

2. **Create a virtual environment**:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Running the Server

### Local Development

Run the FastAPI server with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /api/execute_task

Execute a task by planning agent actions, executing them, and synthesizing results.

**Request Body**:
```json
{
  "task": "Get details about PR #123 in the repository owner/repo",
  "context": {
    "owner": "owner",
    "repo": "repo"
  }
}
```

**Response** (200 OK):
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "Get details about PR #123 in the repository owner/repo",
  "plan": [
    {
      "step_id": 0,
      "agent": "GithubAgent",
      "action": "get_pr",
      "args": {
        "owner": "owner",
        "repo": "repo",
        "number": 123
      }
    }
  ],
  "trace": [
    {
      "step_id": 0,
      "agent": "GithubAgent",
      "action": "get_pr",
      "request": {
        "owner": "owner",
        "repo": "repo",
        "number": 123
      },
      "response_summary": "{\"title\": \"PR Title\", \"author\": \"user\", ...}",
      "duration_ms": 450,
      "truncated": false,
      "warnings": []
    }
  ],
  "final_result": {
    "type": "structured",
    "content": {
      "summary": "PR #123 details retrieved successfully",
      "recommended_next_steps": ["Review the PR changes", "Check test coverage"],
      "warnings": []
    }
  },
  "warnings": []
}
```

### GET /api/agents

List available agents and their capabilities.

**Response** (200 OK):
```json
{
  "GithubAgent": {
    "name": "GithubAgent",
    "description": "Read-only GitHub operations (PRs, commits, files)",
    "actions": ["get_pr", "list_recent_commits", "get_file"]
  },
  "AWSAgent": {
    "name": "AWSAgent",
    "description": "Read-only AWS operations (S3, EC2)",
    "actions": ["list_s3_buckets", "describe_ec2_instances", "get_s3_object_head"]
  },
  "JiraAgent": {
    "name": "JiraAgent",
    "description": "Read-only JIRA operations (issues, search)",
    "actions": ["get_issue", "search_issues"]
  }
}
```

## Access Agents

### GithubAgent

- `get_pr(owner, repo, number)` - Returns PR title, author, body, list of changed files (paths), and small unified diff hunks (truncated if long)
- `list_recent_commits(owner, repo, branch, limit=20)` - Returns commit messages and authors
- `get_file(owner, repo, path, ref)` - Returns file content up to a safe max length

### AWSAgent

- `list_s3_buckets()` - List bucket names (or limited sample)
- `describe_ec2_instances(region)` - List instance IDs and basic metadata
- `get_s3_object_head(bucket, key)` - Returns metadata only (no object download)

### JiraAgent

- `get_issue(issue_key)` - Returns title, description, reporter, status, comments (first N)
- `search_issues(jql, limit=20)` - List of issues with key and summary

## Example Requests

### Example 1: Get GitHub PR Details

```bash
curl -X POST "http://localhost:8000/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Get details about PR #123 in the repository owner/repo",
    "context": {
      "owner": "owner",
      "repo": "repo"
    }
  }'
```

### Example 2: List Recent Commits

```bash
curl -X POST "http://localhost:8000/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "List the last 10 commits from the main branch in owner/repo",
    "context": {
      "owner": "owner",
      "repo": "repo",
      "branch": "main"
    }
  }'
```

### Example 3: Get JIRA Issue

```bash
curl -X POST "http://localhost:8000/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Get details about JIRA issue PROJ-123",
    "context": {}
  }'
```

### Example 4: List AWS S3 Buckets

```bash
curl -X POST "http://localhost:8000/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "List all S3 buckets in my AWS account",
    "context": {}
  }'
```

## Logging & Tracing

- **Structured Logging**: The application uses structlog for structured JSON logging. Logs include timestamps, request IDs, step IDs, agent names, actions, durations, and status.
- **Trace Persistence**: Execution traces are saved to the `traces/` directory as JSON files named by request ID (`{request_id}.json`). These traces include plan steps, execution traces, and final results (but exclude raw LLM prompts and full tool outputs for security).

## Validation & Safety

- **Plan Validation**: The planning LLM's plan is validated against a whitelist of allowed agents and actions. Disallowed actions result in a clear error.
- **Input Sanitization**: Network and file path arguments are sanitized to prevent SSRF and local file access.
- **Read-Only Semantics**: Code never calls GitHub/Git write APIs or JIRA write endpoints. If a write is implied, the planning LLM returns a suggested action but does not execute it.
- **Rate Limiting**: LLM calls are rate-limited with a simple in-process semaphore limiting concurrency to 1.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration and settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # Base agent class
│   │   ├── github_agent.py     # GitHub agent implementation
│   │   ├── aws_agent.py        # AWS agent implementation
│   │   └── jira_agent.py       # JIRA agent implementation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py       # LLM client wrapper
│   │   ├── llm_planner.py      # LLM planner implementation
│   │   ├── plan_validator.py   # Plan validation logic
│   │   └── orchestrator.py     # Task orchestration logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic schemas
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Logging configuration
│       ├── sanitization.py     # Input sanitization utilities
│       └── trace_persistence.py # Trace persistence utilities
├── traces/                     # Trace files (created at runtime)
├── .env.example                # Environment variables template
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Task executed successfully
- `400 Bad Request`: Invalid request body or validation error
- `500 Internal Server Error`: Task execution failed or unexpected error

Errors include detailed messages in the response body and are logged with structured logging.

## Limitations

- **Read-Only Operations**: The system only performs read-only operations. Write operations are not supported.
- **Sequential Execution**: Plan steps are executed sequentially (not in parallel).
- **Single LLM**: Uses a single planning LLM for both planning and synthesis.
- **Local Execution**: Designed to run locally without Docker (though Docker can be added if needed).

## License

This is a prototype/minimal implementation for learning agentic flows.

