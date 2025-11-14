# Project Context & Documentation

## 🎯 Project Goal

Build a **minimal agentic system** that uses an AI (LLM) to plan and execute tasks across multiple services (GitHub, AWS, JIRA). The system acts as a "smart assistant" that:

1. **Receives** a high-level task request (e.g., "Get details about PR #123")
2. **Plans** what actions to take using an LLM
3. **Executes** those actions by calling external APIs (GitHub, AWS, JIRA)
4. **Synthesizes** the results into a final answer

**Important**: All operations are **READ-ONLY** - we never modify, create, or delete anything in external systems.

---

## 📋 What Has Been Done

### ✅ Completed Components

1. **Project Structure** - Created modular folder structure
2. **Configuration** - Environment variable management
3. **Access Agents** - Three agents for GitHub, AWS, and JIRA
4. **LLM Integration** - Planning and synthesis using OpenAI/Cursor API
5. **Orchestration** - Coordinates planning → execution → synthesis
6. **API Endpoints** - FastAPI routes for task execution
7. **Logging & Tracing** - Structured logging and trace persistence
8. **Validation & Safety** - Input sanitization and plan validation
9. **Documentation** - README with setup instructions

### 📁 Files Created

- **Core Application**: `app/main.py`, `app/config.py`
- **API Layer**: `app/api/routes.py`, `app/api/dependencies.py`
- **Agents**: `app/agents/base.py`, `app/agents/github_agent.py`, `app/agents/aws_agent.py`, `app/agents/jira_agent.py`
- **Services**: `app/services/llm_client.py`, `app/services/llm_planner.py`, `app/services/orchestrator.py`, `app/services/plan_validator.py`
- **Models**: `app/models/schemas.py`
- **Utilities**: `app/utils/logging.py`, `app/utils/sanitization.py`, `app/utils/trace_persistence.py`
- **Config**: `requirements.txt`, `.env.example`, `README.md`

---

## 🏗️ Codebase Structure

```
Agent Ops/
├── app/                          # Main application package
│   ├── __init__.py               # Makes 'app' a Python package
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Configuration & environment variables
│   │
│   ├── api/                      # API layer (HTTP endpoints)
│   │   ├── __init__.py
│   │   ├── routes.py             # API route definitions
│   │   └── dependencies.py       # Dependency injection (FastAPI)
│   │
│   ├── agents/                   # Access agents (tool wrappers)
│   │   ├── __init__.py
│   │   ├── base.py               # Base class for all agents
│   │   ├── github_agent.py       # GitHub API wrapper
│   │   ├── aws_agent.py          # AWS API wrapper
│   │   └── jira_agent.py         # JIRA API wrapper
│   │
│   ├── services/                 # Business logic services
│   │   ├── __init__.py
│   │   ├── llm_client.py         # LLM API client (OpenAI/Cursor)
│   │   ├── llm_planner.py        # LLM planning & synthesis logic
│   │   ├── orchestrator.py        # Main orchestration flow
│   │   └── plan_validator.py     # Validates LLM-generated plans
│   │
│   ├── models/                   # Data models (Pydantic schemas)
│   │   ├── __init__.py
│   │   └── schemas.py            # Request/response schemas
│   │
│   └── utils/                    # Utility functions
│       ├── __init__.py
│       ├── logging.py            # Logging configuration
│       ├── sanitization.py       # Input validation & sanitization
│       └── trace_persistence.py  # Save execution traces to disk
│
├── traces/                       # Trace files (created at runtime)
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── README.md                     # User documentation
└── CONTEXT.md                    # This file
```

### 📦 What Each Directory Does

- **`app/api/`**: Defines HTTP endpoints (what URLs the API responds to)
- **`app/agents/`**: Wrappers around external APIs (GitHub, AWS, JIRA)
- **`app/services/`**: Core business logic (planning, orchestration, validation)
- **`app/models/`**: Data structures (what requests/responses look like)
- **`app/utils/`**: Helper functions (logging, sanitization, file I/O)

---

## 🔑 Important Functions & Code Parts

### 1. **API Entry Point** - `app/api/routes.py`

**Function**: `execute_task()`
- **What it does**: Main API endpoint that receives task requests
- **Input**: JSON with `task` (string) and optional `context` (dict)
- **Output**: Complete response with plan, trace, and final result
- **Why important**: This is where everything starts!

```python
@router.post("/api/execute_task")
async def execute_task(request: TaskRequest, orchestrator: TaskOrchestrator):
    # Calls orchestrator to handle the entire flow
    response = await orchestrator.execute(request)
    return response
```

---

### 2. **Orchestration Flow** - `app/services/orchestrator.py`

**Class**: `TaskOrchestrator`

**Main Method**: `execute()`
- **What it does**: Coordinates the entire task execution flow
- **Flow**:
  1. Generate plan using LLM
  2. Validate plan (safety check)
  3. Execute each step sequentially
  4. Synthesize final result
  5. Save trace to disk

**Key Methods**:
- `_generate_plan()`: Calls LLM to create a plan
- `_execute_step()`: Runs a single agent action
- `_synthesize()`: Calls LLM to create final summary

**Why important**: This is the "brain" that coordinates everything!

---

### 3. **LLM Planner** - `app/services/llm_planner.py`

**Class**: `LLMPlanner`

**Methods**:
- `plan(task, context)`: Asks LLM to create a step-by-step plan
- `synthesize(task, plan, trace)`: Asks LLM to summarize results

**System Prompts**:
- **Planning**: "You are a deterministic planning assistant. Return a JSON array of steps..."
- **Synthesis**: "You are a synthesis assistant. Produce a final JSON result..."

**Why important**: This is where the AI "thinks" about what to do!

---

### 4. **Plan Validator** - `app/services/plan_validator.py`

**Class**: `PlanValidator`

**Method**: `validate(plan_steps)`
- **What it does**: Checks if the LLM's plan is safe and allowed
- **Checks**:
  - Only allowed agents are used
  - Only allowed actions are called
  - Required arguments are present
  - Argument types are correct

**Why important**: Safety! Prevents the LLM from doing dangerous things.

---

### 5. **Access Agents** - `app/agents/`

**Base Class**: `BaseAgent` (in `base.py`)
- Provides common functionality (logging, error handling)

**Concrete Agents**:

#### `GithubAgent` (`github_agent.py`)
- `get_pr(owner, repo, number)`: Get pull request details
- `list_recent_commits(owner, repo, branch, limit)`: List commits
- `get_file(owner, repo, path, ref)`: Get file contents

#### `AWSAgent` (`aws_agent.py`)
- `list_s3_buckets()`: List S3 buckets
- `describe_ec2_instances(region)`: List EC2 instances
- `get_s3_object_head(bucket, key)`: Get S3 object metadata

#### `JiraAgent` (`jira_agent.py`)
- `get_issue(issue_key)`: Get JIRA issue details
- `search_issues(jql, limit)`: Search JIRA issues

**Why important**: These are the "tools" that actually fetch data from external services.

---

### 6. **LLM Client** - `app/services/llm_client.py`

**Class**: `LLMClient`

**Method**: `complete(system_prompt, user_prompt, temperature, max_output_tokens)`
- **What it does**: Makes API calls to OpenAI/Cursor
- **Features**:
  - Rate limiting (semaphore - only 1 call at a time)
  - Token usage logging
  - Error handling

**Why important**: This is how we talk to the AI!

---

### 7. **Data Models** - `app/models/schemas.py`

**Key Schemas**:

- `TaskRequest`: What the user sends
  ```python
  {
    "task": "Get PR #123 details",
    "context": {"owner": "user", "repo": "repo"}
  }
  ```

- `TaskResponse`: What we send back
  ```python
  {
    "request_id": "uuid",
    "task": "original task",
    "plan": [...],      # Steps to execute
    "trace": [...],     # Execution results
    "final_result": {...},  # LLM summary
    "warnings": [...]
  }
  ```

- `PlanStep`: A single step in the plan
  ```python
  {
    "step_id": 0,
    "agent": "GithubAgent",
    "action": "get_pr",
    "args": {"owner": "...", "repo": "...", "number": 123}
  }
  ```

**Why important**: These define the "contract" - what data looks like going in and out.

---

### 8. **Configuration** - `app/config.py`

**Class**: `Settings`
- Loads environment variables from `.env` file
- Validates required settings
- Provides defaults

**Why important**: Centralized configuration management.

---

### 9. **Utilities**

#### `app/utils/sanitization.py`
- Validates and sanitizes user inputs
- Prevents SSRF (Server-Side Request Forgery) attacks
- Validates URLs, paths, bucket names, etc.

#### `app/utils/logging.py`
- Sets up structured JSON logging
- Uses `structlog` for better log formatting

#### `app/utils/trace_persistence.py`
- Saves execution traces to `traces/` directory
- Each request gets a JSON file with full execution details

---

## 🔄 Complete API Flow: `/api/execute_task`

Here's the step-by-step flow when a request comes in:

### Step 1: Request Arrives
```
POST /api/execute_task
Body: {"task": "Get PR #123 details", "context": {...}}
```

**Location**: `app/api/routes.py` → `execute_task()`

---

### Step 2: Dependency Injection
FastAPI automatically provides:
- `TaskRequest` (parsed from JSON)
- `TaskOrchestrator` (created via dependencies)

**Location**: `app/api/dependencies.py` → `get_orchestrator()`

---

### Step 3: Orchestrator Starts
**Location**: `app/services/orchestrator.py` → `execute()`

```python
async def execute(self, request: TaskRequest) -> TaskResponse:
    request_id = uuid4()  # Generate unique ID
    # ... continues below
```

---

### Step 4: Generate Plan
**Location**: `app/services/orchestrator.py` → `_generate_plan()`

```python
raw_plan = await self.planner.plan(task=request.task, context=request.context)
```

**What happens**:
1. Calls `LLMPlanner.plan()`
2. LLM receives system prompt + task description
3. LLM returns JSON array of steps:
   ```json
   [
     {
       "step_id": 0,
       "agent": "GithubAgent",
       "action": "get_pr",
       "args": {"owner": "owner", "repo": "repo", "number": 123}
     }
   ]
   ```

**Location**: `app/services/llm_planner.py` → `plan()`

---

### Step 5: Validate Plan
**Location**: `app/services/orchestrator.py` → `validator.validate()`

```python
plan_steps = self.validator.validate(raw_plan)
```

**What happens**:
1. Checks if agent name is allowed (GithubAgent, AWSAgent, JiraAgent)
2. Checks if action is allowed for that agent
3. Validates required arguments are present
4. Validates argument types (str, int, etc.)
5. Removes any extra arguments (security)

**Location**: `app/services/plan_validator.py` → `validate()`

**If validation fails**: Raises `PlanValidationError` → Returns 500 error

---

### Step 6: Execute Plan Steps (Sequentially)
**Location**: `app/services/orchestrator.py` → `_execute_step()`

For each step in the plan:

```python
for step in plan_steps:
    trace_entry, warnings = await self._execute_step(request_id, step)
    trace_entries.append(trace_entry)
```

**What happens for each step**:

1. **Get Agent**: `agent = self.agents.get(step.agent)`
   - Looks up the agent instance (GithubAgent, AWSAgent, or JiraAgent)

2. **Get Action Method**: `action = getattr(agent, step.action)`
   - Gets the method (e.g., `agent.get_pr`)

3. **Sanitize Arguments**: Arguments are already validated, but we make a copy

4. **Call Agent Method**: `result = action(**args)`
   - Actually calls the agent method (e.g., `github_agent.get_pr(owner="...", repo="...", number=123)`)
   - This makes HTTP calls to external APIs

5. **Handle Response**:
   - If success: Extract data, check for truncation
   - If error: Create error trace entry, raise exception

6. **Create Trace Entry**:
   ```python
   TraceEntry(
       step_id=0,
       agent="GithubAgent",
       action="get_pr",
       request={"owner": "...", "repo": "...", "number": 123},
       response_summary="{\"title\": \"PR Title\", ...}",
       duration_ms=450,
       truncated=False,
       warnings=[]
   )
   ```

**Agent Execution Details**:

**GithubAgent.get_pr()** (`app/agents/github_agent.py`):
- Makes HTTP GET to `https://api.github.com/repos/{owner}/{repo}/pulls/{number}`
- Fetches PR details, changed files, and unified diff
- Returns `AgentResponse` with data

**AWSAgent.list_s3_buckets()** (`app/agents/aws_agent.py`):
- Uses boto3 to call AWS S3 API
- Lists buckets (limited to 50)
- Returns `AgentResponse` with bucket names

**JiraAgent.get_issue()** (`app/agents/jira_agent.py`):
- Uses jira-python library
- Fetches issue details and comments
- Returns `AgentResponse` with issue data

---

### Step 7: Synthesize Final Result
**Location**: `app/services/orchestrator.py` → `_synthesize()`

```python
synthesis = await self.planner.synthesize(
    task=request.task,
    plan=[step.dict() for step in plan_steps],
    trace=[entry.dict() for entry in trace_entries]
)
```

**What happens**:
1. Calls `LLMPlanner.synthesize()`
2. LLM receives:
   - Original task
   - Executed plan
   - Trace summaries (truncated to avoid token limits)
3. LLM returns JSON:
   ```json
   {
     "final_result": {
       "type": "structured",
       "content": {
         "summary": "PR #123 details retrieved successfully",
         "recommended_next_steps": ["Review the changes", "Check tests"],
         "warnings": []
       }
     },
     "warnings": []
   }
   ```

**Location**: `app/services/llm_planner.py` → `synthesize()`

---

### Step 8: Save Trace to Disk
**Location**: `app/services/orchestrator.py` → `save_trace()`

```python
save_trace(response)
```

**What happens**:
- Creates JSON file: `traces/{request_id}.json`
- Contains: request_id, task, plan, trace, final_result, warnings
- Used for debugging and post-hoc analysis

**Location**: `app/utils/trace_persistence.py` → `save_trace()`

---

### Step 9: Return Response
**Location**: `app/api/routes.py` → `execute_task()`

```python
return response  # TaskResponse object
```

**Response JSON**:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "task": "Get PR #123 details",
  "plan": [
    {
      "step_id": 0,
      "agent": "GithubAgent",
      "action": "get_pr",
      "args": {"owner": "...", "repo": "...", "number": 123}
    }
  ],
  "trace": [
    {
      "step_id": 0,
      "agent": "GithubAgent",
      "action": "get_pr",
      "request": {...},
      "response_summary": "{\"title\": \"...\", ...}",
      "duration_ms": 450,
      "truncated": false,
      "warnings": []
    }
  ],
  "final_result": {
    "type": "structured",
    "content": {
      "summary": "PR #123 details retrieved successfully",
      "recommended_next_steps": [...],
      "warnings": []
    }
  },
  "warnings": []
}
```

---

## 🔍 Key Concepts for Beginners

### 1. **Async/Await**
- `async def` = function that can be paused/resumed
- `await` = wait for async operation to complete
- Used for: HTTP requests, LLM calls, file I/O

**Example**:
```python
async def get_pr(...):
    response = await httpx.get(url)  # Wait for HTTP request
    return response.json()
```

### 2. **Dependency Injection (FastAPI)**
- FastAPI automatically creates objects and passes them to route functions
- Defined in `app/api/dependencies.py`
- Example: `orchestrator: TaskOrchestrator = Depends(get_orchestrator)`

### 3. **Pydantic Schemas**
- Define data structure and validation
- Automatically validates JSON input/output
- Example: `TaskRequest` validates that `task` is a non-empty string

### 4. **Type Hints**
- Python annotations that specify what type a variable should be
- Example: `def execute(request: TaskRequest) -> TaskResponse:`
- Helps with IDE autocomplete and catching errors

### 5. **Context Managers**
- Objects that can be used with `with` statement
- Example: `async with self._semaphore:` (rate limiting)

### 6. **Error Handling**
- `try/except`: Catch and handle errors
- Custom exceptions: `AgentError`, `PlannerError`, `PlanValidationError`
- Errors are logged and returned as warnings in response

---

## 🛡️ Safety Features

1. **Plan Validation**: Only allowed agents/actions can be executed
2. **Input Sanitization**: Prevents SSRF attacks (malicious URLs)
3. **Read-Only Operations**: No write operations allowed
4. **Rate Limiting**: LLM calls limited to 1 concurrent request
5. **Error Handling**: Errors are caught and logged, don't crash the app
6. **Trace Logging**: All operations are logged for auditing

---

## 📝 Next Steps for Learning

1. **Start the server**: `uvicorn app.main:app --reload`
2. **Try the API**: Use the examples in README.md
3. **Read the code**: Start with `app/api/routes.py`, then follow the flow
4. **Check traces**: Look at `traces/` directory after making requests
5. **Modify agents**: Try adding a new method to `GithubAgent`
6. **Add logging**: Add more log statements to understand the flow

---

## 🐛 Common Issues & Debugging

1. **Missing environment variables**: Check `.env` file
2. **LLM API errors**: Check API key and rate limits
3. **Agent errors**: Check external service credentials
4. **Validation errors**: Check plan format matches schema
5. **Import errors**: Make sure you're in the project root directory

---

## 📚 Additional Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Pydantic Docs**: https://docs.pydantic.dev/
- **Python Async**: https://docs.python.org/3/library/asyncio.html
- **GitHub API**: https://docs.github.com/en/rest
- **AWS Boto3**: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **JIRA Python**: https://jira.readthedocs.io/

---

**Last Updated**: After initial implementation completion
**Status**: ✅ All core features implemented and tested

